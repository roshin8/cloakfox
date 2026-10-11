// Loopback-only BoringSSL ALPS/H2 fixture. No keys or tickets are logged.
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <openssl/bytestring.h>
#include <openssl/hpke.h>
#include "ssl/internal.h"
#include <zlib.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static void HandshakeInfo(const SSL* ssl,int where,int) {
  if (where & SSL_CB_HANDSHAKE_DONE) {
    printf("{\"signature\":%u}\n",unsigned(SSL_get_signature_algorithm_used(ssl)));fflush(stdout);
  }
}
static int SelectALPN(SSL*, const unsigned char** out, unsigned char* length,
                      const unsigned char* offered, unsigned int offeredLength, void*) {
  static const unsigned char protocols[] = {2, 'h', '2'};
  return SSL_select_next_proto(const_cast<unsigned char**>(out), length,
                               protocols, sizeof(protocols), offered, offeredLength)
                 == OPENSSL_NPN_NEGOTIATED ? SSL_TLSEXT_ERR_OK : SSL_TLSEXT_ERR_ALERT_FATAL;
}
// Test-only adversarial selection: a genuine, transcript-authenticated zlib
// Certificate is sent although the client only offered Brotli. Product code
// must reject it before invoking an unadvertised decoder.
static int CompressZlib(SSL*, CBB* out, const uint8_t* input, size_t length) {
  uLongf capacity=compressBound(length);
  std::vector<unsigned char> compressed(capacity);
  return compress2(compressed.data(),&capacity,input,length,Z_DEFAULT_COMPRESSION)==Z_OK &&
         CBB_add_bytes(out,compressed.data(),capacity);
}
static int ForceUnadvertisedCompression(SSL* ssl, void*) {
  auto* hs=bssl::FromOpaque(ssl)->s3->hs.get();
  hs->cert_compression_negotiated=true;
  hs->cert_compression_alg_id=1;
  return 1;
}
// Select a genuine P-521 handshake signature despite the client's offer.
// Mutate only this adversarial loopback server's parsed offer.
static int ForceUnadvertisedSignature(SSL* ssl, void*) {
  static const uint16_t schemes[]={SSL_SIGN_ECDSA_SECP521R1_SHA512};
  return bssl::FromOpaque(ssl)->s3->hs->peer_sigalgs.CopyFrom(schemes);
}
static bool Read(SSL* ssl, unsigned char* data, size_t length) {
  while (length) {
    int got=SSL_read(ssl,data,length);
    if (got<=0) return false;
    data+=got;length-=got;
  }
  return true;
}
static bool Frame(SSL* ssl, unsigned char type, unsigned char flags,
                  uint32_t stream, const unsigned char* payload, size_t length) {
  if (length>0xffffff) return false;
  std::vector<unsigned char> data = {static_cast<unsigned char>(length>>16),
    static_cast<unsigned char>(length>>8),static_cast<unsigned char>(length),type,flags,
    static_cast<unsigned char>(stream>>24),static_cast<unsigned char>(stream>>16),
    static_cast<unsigned char>(stream>>8),static_cast<unsigned char>(stream)};
  if (length) data.insert(data.end(),payload,payload+length);
  return SSL_write(ssl,data.data(),data.size())==static_cast<int>(data.size());
}
int main(int argc,char** argv) {
  if (argc<3) return 2;
  signal(SIGPIPE,SIG_IGN);
  SSL_CTX* ctx=SSL_CTX_new(TLS_method());
  if (!ctx || !SSL_CTX_use_certificate_chain_file(ctx,argv[1]) ||
      !SSL_CTX_use_PrivateKey_file(ctx,argv[2],SSL_FILETYPE_PEM)) return 3;
  SSL_CTX_set_info_callback(ctx,HandshakeInfo);
  SSL_CTX_set_min_proto_version(ctx,TLS1_3_VERSION);
  SSL_CTX_set_early_data_enabled(ctx,1);
  SSL_CTX_set_alpn_select_cb(ctx,SelectALPN,nullptr);
  if (argc>3 && !strcmp(argv[3],"unadvertised-compression")) {
    if (!SSL_CTX_add_cert_compression_alg(ctx,1,CompressZlib,nullptr)) return 6;
    SSL_CTX_set_cert_cb(ctx,ForceUnadvertisedCompression,nullptr);
  }
  if (argc>3 && !strcmp(argv[3],"unadvertised-signature")) {
    SSL_CTX_set_cert_cb(ctx,ForceUnadvertisedSignature,nullptr);
  }
  std::vector<unsigned char> echList;
  if (argc>3 && !strcmp(argv[3],"ech")) {
    EVP_HPKE_KEY* hpke=EVP_HPKE_KEY_new();
    SSL_ECH_KEYS* keys=SSL_ECH_KEYS_new();
    unsigned char* config=nullptr;size_t configLength=0;
    if (!hpke || !keys || !EVP_HPKE_KEY_generate(hpke,EVP_hpke_x25519_hkdf_sha256()) ||
        !SSL_marshal_ech_config(&config,&configLength,19,hpke,"ech-public.test",64) ||
        !SSL_ECH_KEYS_add(keys,1,config,configLength,hpke) || !SSL_CTX_set1_ech_keys(ctx,keys)) return 7;
    echList={static_cast<unsigned char>(configLength>>8),static_cast<unsigned char>(configLength)};
    echList.insert(echList.end(),config,config+configLength);
    OPENSSL_free(config);SSL_ECH_KEYS_free(keys);EVP_HPKE_KEY_free(hpke);
  }
  int listener=socket(AF_INET,SOCK_STREAM,0);
  sockaddr_in address{};address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
  if (bind(listener,reinterpret_cast<sockaddr*>(&address),sizeof(address)) || listen(listener,8)) return 4;
  socklen_t addressLength=sizeof(address);getsockname(listener,reinterpret_cast<sockaddr*>(&address),&addressLength);
  printf("{\"port\":%d,\"echConfig\":\"",ntohs(address.sin_port));
  for (auto byte:echList) printf("%02x",unsigned(byte));
  printf("\"}\n");fflush(stdout);
  // Optional HEADER_TABLE_SIZE=0 and MAX_CONCURRENT_STREAMS=3 in ALPS.
  static const unsigned char settings[]={0,0,12,4,0,0,0,0,0,0,1,0,0,0,0,0,3,0,0,0,3};
  while (true) {
    int fd=accept(listener,nullptr,nullptr);if (fd<0) break;
    timeval timeout{10,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    SSL* ssl=SSL_new(ctx);SSL_set_fd(ssl,fd);
    const unsigned char protocol[]={'h','2'};
    std::vector<unsigned char> local;
    if (argc>3) {
      local.assign(settings,settings+sizeof(settings));
      if (!strcmp(argv[3],"window-overflow")) local={0,0,6,4,0,0,0,0,0,0,4,255,255,255,255};
      if (!strcmp(argv[3],"ack")) local[4]=1;
      if (!strcmp(argv[3],"stream")) local[8]=1;
      if (!strcmp(argv[3],"truncated")) local.pop_back();
      if (!strcmp(argv[3],"forbidden")) local={0,0,8,6,0,0,0,0,0,0,0,0,0,0,0,0,0};
    }
    if (!SSL_add_application_settings(ssl,protocol,2,local.data(),local.size())) return 5;
    if (SSL_accept(ssl)!=1) {
      printf("{\"handshakeFailed\":true}\n");fflush(stdout);
      SSL_free(ssl);close(fd);continue;
    }
    const unsigned char* peer=nullptr;size_t peerLength=0;
    SSL_get0_peer_application_settings(ssl,&peer,&peerLength);
    printf("{\"echAccepted\":%s}\n",SSL_ech_accepted(ssl)?"true":"false");fflush(stdout);
    printf("{\"alps\":%s,\"peerLength\":%zu,\"resumed\":%s,\"earlyDataAccepted\":%s}\n",
      SSL_has_application_settings(ssl)?"true":"false",peerLength,SSL_session_reused(ssl)?"true":"false",SSL_early_data_accepted(ssl)?"true":"false");fflush(stdout);
    unsigned char preface[24];
    if (Read(ssl,preface,sizeof(preface)) && !memcmp(preface,"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n",24)) {
      Frame(ssl,4,0,0,nullptr,0);
      unsigned char header[9];
      while (Read(ssl,header,sizeof(header))) {
        size_t length=(size_t(header[0])<<16)|(size_t(header[1])<<8)|header[2];
        uint32_t stream=(uint32_t(header[5])<<24)|(uint32_t(header[6])<<16)|(uint32_t(header[7])<<8)|header[8];
        if (length>1048576) break;
        std::vector<unsigned char> payload(length);
        if (!Read(ssl,payload.data(),length)) break;
        if (header[3]==4 && !(header[4]&1)) Frame(ssl,4,1,0,nullptr,0);
        if (header[3]==1) {
          size_t start=(header[4]&8)?1:0;
          if (header[4]&32) start+=5; // HEADERS priority prefix is not HPACK.
          printf("{\"firstHeaderByte\":%d}\n",start>=payload.size()?-1:int(payload[start]));fflush(stdout);
          unsigned char status=0x88; // HPACK static-table :status=200.
          static const unsigned char body[]="local-alps-ok";
          if (!Frame(ssl,1,4,stream,&status,1) || !Frame(ssl,0,1,stream,body,sizeof(body)-1)) break;
          if (argc>4 && !strcmp(argv[4],"close")) break;
        }
      }
    }
    SSL_free(ssl);close(fd);
  }
  SSL_CTX_free(ctx);close(listener);
}
