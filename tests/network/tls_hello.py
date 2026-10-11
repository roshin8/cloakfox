"""Structural TLS ClientHello decoder; excludes secrets and GREASE.
"""
import struct

def words(data):
    assert len(data) % 2 == 0
    return [int.from_bytes(data[i:i+2], 'big') for i in range(0,len(data),2)]


def grease(value):
    return value & 0x0f0f == 0x0a0a and value >> 8 == value & 255


def client_hello(data):
    """Parse an assembled TLS ClientHello handshake, with strict lengths."""
    assert data[0] == 1
    assert len(data) >= 4+int.from_bytes(data[1:4],'big')
    body=data[4:4+int.from_bytes(data[1:4],'big')]; pos=34
    legacy=int.from_bytes(body[:2],'big')
    pos+=1+body[pos]
    size=int.from_bytes(body[pos:pos+2],'big'); pos+=2
    ciphers=[x for x in words(body[pos:pos+size]) if not grease(x)]; pos+=size
    pos+=1+body[pos]
    total=int.from_bytes(body[pos:pos+2],'big'); pos+=2; end=pos+total
    assert end == len(body)
    result={'legacyVersion':legacy,'ciphers':ciphers,'extensions':[]}
    while pos<end:
        kind,size=struct.unpack('!HH',body[pos:pos+4]); pos+=4
        value=body[pos:pos+size]; pos+=size
        assert len(value)==size
        if grease(kind): continue
        # Padding length and contents are intentionally not fingerprinted.
        result['extensions'].append(kind)
        if kind in (10,13,50):
            assert int.from_bytes(value[:2],'big')==len(value)-2
            result[{10:'groups',13:'signatures',50:'certificateSignatures'}[kind]]=[x for x in words(value[2:]) if not grease(x)]
        if kind==43:
            assert value[0]==len(value)-1
            result['versions']=[x for x in words(value[1:]) if not grease(x)]
        if kind==16:
            length=int.from_bytes(value[:2],'big'); assert length==len(value)-2
            cursor=2; names=[]
            while cursor<len(value):
                n=value[cursor];cursor+=1; names.append(value[cursor:cursor+n].decode('ascii'));cursor+=n
            result['alpn']=names
        if kind==51:
            cursor=2; groups=[]
            while cursor<len(value):
                group,n=struct.unpack('!HH',value[cursor:cursor+4]);cursor+=4+n
                if not grease(group):groups.append(group)
            result['keyShareGroups']=groups
    return result
