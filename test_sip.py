import socket
import time

sip_invite = """INVITE sip:test_call@127.0.0.1 SIP/2.0
Via: SIP/2.0/UDP 127.0.0.1:5061;branch=z9hG4bK-1234
Max-Forwards: 70
To: <sip:test_call@127.0.0.1>
From: <sip:tester@127.0.0.1>;tag=1928301774
Call-ID: a84b4c76e66710@127.0.0.1
CSeq: 1 INVITE
Contact: <sip:tester@127.0.0.1:5061>
Content-Type: application/sdp
Content-Length: 129

v=0
o=user1 53655765 2353687637 IN IP4 127.0.0.1
s=-
c=IN IP4 127.0.0.1
t=0 0
m=audio 6000 RTP/AVP 0
a=rtpmap:0 PCMU/8000
"""

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 5061))

sock.sendto(sip_invite.encode('utf-8').replace(b'\n', b'\r\n'), ("127.0.0.1", 5060))
print("Sent SIP INVITE to 127.0.0.1:5060")

sock.settimeout(5)
try:
    while True:
        data, addr = sock.recvfrom(4096)
        print("Received:", data.decode('utf-8'))
        if b"200 OK" in data:
            # Send ACK
            ack = """ACK sip:test_call@127.0.0.1 SIP/2.0
Via: SIP/2.0/UDP 127.0.0.1:5061;branch=z9hG4bK-1234-ack
Max-Forwards: 70
To: <sip:test_call@127.0.0.1>;tag=REPLACE_TAG
From: <sip:tester@127.0.0.1>;tag=1928301774
Call-ID: a84b4c76e66710@127.0.0.1
CSeq: 1 ACK
Contact: <sip:tester@127.0.0.1:5061>
Content-Length: 0
"""
            sock.sendto(ack.encode('utf-8').replace(b'\n', b'\r\n'), ("127.0.0.1", 5060))
            print("Sent ACK. Call is active.")
            break
except socket.timeout:
    print("Timeout waiting for response.")

# Keep call open for 5 seconds
time.sleep(5)

# Send BYE
bye = """BYE sip:test_call@127.0.0.1 SIP/2.0
Via: SIP/2.0/UDP 127.0.0.1:5061;branch=z9hG4bK-1235
Max-Forwards: 70
To: <sip:test_call@127.0.0.1>
From: <sip:tester@127.0.0.1>;tag=1928301774
Call-ID: a84b4c76e66710@127.0.0.1
CSeq: 2 BYE
Content-Length: 0
"""
sock.sendto(bye.encode('utf-8').replace(b'\n', b'\r\n'), ("127.0.0.1", 5060))
print("Sent BYE.")
