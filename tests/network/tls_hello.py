"""Structural TLS ClientHello decoder; excludes secrets and GREASE.
"""
import struct

def words(data):
    assert len(data) % 2 == 0
    return [int.from_bytes(data[i:i+2], 'big') for i in range(0,len(data),2)]


def grease(value):
    return value & 0x0f0f == 0x0a0a and value >> 8 == value & 255


def client_hello(data, detailed=False):
    """Parse an assembled TLS ClientHello handshake, with strict lengths."""
    assert data[0] == 1
    assert len(data) >= 4+int.from_bytes(data[1:4],'big')
    body=data[4:4+int.from_bytes(data[1:4],'big')]; pos=34
    legacy=int.from_bytes(body[:2],'big')
    session_length = body[pos]
    pos+=1+session_length
    size=int.from_bytes(body[pos:pos+2],'big'); pos+=2
    raw_ciphers=words(body[pos:pos+size])
    ciphers=[x for x in raw_ciphers if not grease(x)]; pos+=size
    compression=list(body[pos+1:pos+1+body[pos]]); pos+=1+body[pos]
    total=int.from_bytes(body[pos:pos+2],'big'); pos+=2; end=pos+total
    assert end == len(body)
    result={'legacyVersion':legacy,'ciphers':ciphers,'extensions':[]}
    shape={'ciphers': ['GREASE' if grease(x) else x for x in raw_ciphers],
           'sessionIdLength': session_length, 'compressionMethods': compression,
           'extensions': [], 'payloads': {}}
    while pos<end:
        if end-pos < 4:
            raise ValueError('Truncated TLS extension header')
        kind,size=struct.unpack('!HH',body[pos:pos+4]); pos+=4
        if size > end-pos:
            raise ValueError('Truncated TLS extension payload')
        value=body[pos:pos+size]; pos+=size
        assert len(value)==size
        shape['extensions'].append(['GREASE' if grease(kind) else kind, size])
        # Retain only public protocol fields; never SNI, ticket, PSK binders,
        # randoms, ECH ciphertext, key material or connection identifiers.
        if kind in (11, 13, 50, 45, 27, 23, 51764, 17613, 28, 34, 65281):
            shape['payloads'][str(kind)] = value.hex()
        if grease(kind): continue
        # Padding length and contents are intentionally not fingerprinted.
        result['extensions'].append(kind)
        if kind in (10,13,50):
            assert int.from_bytes(value[:2],'big')==len(value)-2
            result[{10:'groups',13:'signatures',50:'certificateSignatures'}[kind]]=[x for x in words(value[2:]) if not grease(x)]
            if kind==10: shape['groups']=['GREASE' if grease(x) else x for x in words(value[2:])]
        if kind==43:
            assert value[0]==len(value)-1
            result['versions']=[x for x in words(value[1:]) if not grease(x)]
            shape['versions']=['GREASE' if grease(x) else x for x in words(value[1:])]
        if kind==16:
            length=int.from_bytes(value[:2],'big'); assert length==len(value)-2
            cursor=2; names=[]
            while cursor<len(value):
                n=value[cursor];cursor+=1
                name=value[cursor:cursor+n];cursor+=n
                assert n and len(name)==n
                if n==2 and grease(int.from_bytes(name,'big')):continue
                names.append(name.decode('ascii'))
            result['alpn']=names
        if kind==51:
            assert int.from_bytes(value[:2], 'big') == len(value)-2
            cursor=2; groups=[]; shares=[]
            while cursor<len(value):
                if len(value)-cursor < 4: raise ValueError('Truncated key share')
                group,n=struct.unpack('!HH',value[cursor:cursor+4]);cursor+=4
                if n > len(value)-cursor: raise ValueError('Truncated key share payload')
                cursor+=n
                shares.append(['GREASE' if grease(group) else group, n])
                if not grease(group):groups.append(group)
            result['keyShareGroups']=groups
            shape['keyShares']=shares
        if kind==65037 and len(value)>=10 and value[0]==0:
            # ECH outer: type, KDF, AEAD, config_id, enc<0..2^16-1>, payload.
            enc_len=int.from_bytes(value[6:8], 'big')
            payload_at=8+enc_len
            if payload_at+2 <= len(value):
                shape['ech']={'kdf': int.from_bytes(value[1:3], 'big'),
                    'aead': int.from_bytes(value[3:5], 'big'), 'encLength': enc_len,
                    'payloadLength': int.from_bytes(value[payload_at:payload_at+2], 'big')}
    if detailed: result['shape']=shape
    return result
