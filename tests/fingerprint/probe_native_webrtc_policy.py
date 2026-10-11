"""Disposable native WebRTC policy/transition and local STUN packet probe.

No external STUN service; run sequentially after native rebuild. Local UDP
positive control must receive traffic before zero-traffic relay result counts.
"""
import json
from pathlib import Path
import socket
import tempfile
import threading

from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch


def policy(driver, ucid, network=0, rtc=0, proxy=''):
    driver.set_context('chrome')
    driver.execute_script('''
      const [ucid, network, rtc, proxy] = arguments;
      const prefix = `cloakfox.container.${ucid}.`;
      Services.prefs.setBoolPref('cloakfox.enabled', false);
      Services.prefs.setIntPref(prefix + 'network_mode', network);
      Services.prefs.setIntPref(prefix + 'webrtc_mode', rtc);
      Services.prefs.setStringPref(prefix + 'proxy_url', proxy);
    ''', ucid, network, rtc, proxy)
    driver.set_context('content')


def open_container(driver, ucid):
    driver.set_context('content')
    previous = set(driver.window_handles)
    driver.set_context('chrome')
    driver.execute_script('''
      const win = Services.wm.getMostRecentWindow('navigator:browser');
      win.gBrowser.selectedTab = win.gBrowser.addTab('about:blank', {
        userContextId: arguments[0],
        triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()
      });
    ''', ucid)
    driver.set_context('content')
    WebDriverWait(driver, 10).until(lambda d: len(set(d.window_handles) - previous) == 1)
    handle = (set(driver.window_handles) - previous).pop()
    driver.switch_to.window(handle)
    driver.set_context('content')
    return handle


def construction(driver):
    return driver.execute_script('''
      try { const pc = new RTCPeerConnection(); pc.close(); return 'allowed'; }
      catch (error) { return error.name; }
    ''')


def packets_during_gathering(driver):
    received = []
    stop = threading.Event()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind(('127.0.0.1', 0))
        server.settimeout(0.1)
        port = server.getsockname()[1]

        def collect():
            while not stop.is_set():
                try:
                    packet, _ = server.recvfrom(8192)
                    received.append(packet)
                except socket.timeout:
                    pass

        worker = threading.Thread(target=collect)
        worker.start()
        try:
            result = driver.execute_async_script('''
              const done = arguments[arguments.length - 1];
              const url = arguments[0];
              (async () => {
                const config = {iceServers:[{urls:url}], iceTransportPolicy:'all'};
                const pc = new RTCPeerConnection(config);
                try {
                  // Attempt to loosen policy through a second native config call.
                  pc.setConfiguration(config);
                  pc.createDataChannel('probe');
                  await pc.setLocalDescription(await pc.createOffer());
                  await new Promise(resolve => setTimeout(resolve, 1800));
                  done({ok:true});
                } finally { pc.close(); }
              })().catch(error => done({error:String(error)}));
            ''', f'stun:127.0.0.1:{port}')
            assert result == {'ok': True}, result
        finally:
            stop.set()
            worker.join(timeout=2)
    return len(received)


def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-rtc-policy-') as directory:
        profile = Path(directory) / 'profile'
        profile.mkdir()
        driver = launch(profile, Path(directory) / 'browser.log')
        try:
            # Permit the loopback interface only in this disposable packet test.
            driver.execute_script("Services.prefs.setBoolPref('media.peerconnection.ice.loopback', true); Services.prefs.setBoolPref('media.peerconnection.ice.default_address_only', false);")
            handle = open_container(driver, 1)
            other = open_container(driver, 2)
            policy(driver, 1)
            policy(driver, 2, rtc=2)
            driver.set_context('content')
            WebDriverWait(driver, 10).until(lambda d: construction(d) != 'allowed')
            driver.switch_to.window(handle)
            assert construction(driver) == 'allowed'
            driver.execute_script('window.savedPC = new RTCPeerConnection();')
            policy(driver, 1, network=1, proxy='socks5://127.0.0.1:9')
            driver.set_context('content')
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return savedPC.signalingState') == 'closed')
            assert construction(driver) != 'allowed', 'Proxy container must disable RTC'
            for network, rtc in ((2, 0), (0, 2), (0, 99), (99, 0)):
                policy(driver, 1, network=network, rtc=rtc)
                driver.set_context('content')
                WebDriverWait(driver, 10).until(lambda d: construction(d) != 'allowed')
            policy(driver, 1)
            driver.set_context('content')
            WebDriverWait(driver, 10).until(lambda d: construction(d) == 'allowed')
            direct = packets_during_gathering(driver)
            assert direct > 0, 'No normal-mode STUN positive control; relay result would be inconclusive'
            driver.execute_script('window.savedPC = new RTCPeerConnection();')
            policy(driver, 1, rtc=1)
            driver.set_context('content')
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return savedPC.signalingState') == 'closed')
            relay = packets_during_gathering(driver)
            assert relay == 0, f'Relay-only mode sent {relay} direct STUN packets'
            driver.execute_script('window.savedPC = new RTCPeerConnection();')
            policy(driver, 1, rtc=1, proxy='changed-route')
            driver.set_context('content')
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return savedPC.signalingState') == 'closed')
            for field in ('network_mode', 'webrtc_mode'):
                policy(driver, 1)
                WebDriverWait(driver, 10).until(lambda d: construction(d) == 'allowed')
                driver.execute_script('window.savedPC = new RTCPeerConnection();')
                driver.set_context('chrome')
                driver.execute_script('''
                  const name = 'cloakfox.container.1.' + arguments[0];
                  Services.prefs.clearUserPref(name);
                  Services.prefs.setStringPref(name, 'invalid-configured-type');
                ''', field)
                driver.set_context('content')
                WebDriverWait(driver, 10).until(lambda d: d.execute_script('return savedPC.signalingState') == 'closed')
                WebDriverWait(driver, 10).until(lambda d: construction(d) != 'allowed')
                driver.set_context('chrome')
                driver.execute_script("Services.prefs.clearUserPref('cloakfox.container.1.' + arguments[0]);", field)
                driver.set_context('content')
            driver.switch_to.window(other)
            assert construction(driver) != 'allowed', 'Other container policy was overwritten'
            print(json.dumps({'normalStunPackets':direct, 'relayStunPackets':relay, 'containerIsolation':True}))
        finally:
            driver.quit()


if __name__ == '__main__':
    main()
