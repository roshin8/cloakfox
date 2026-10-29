"""Verify expanded native and extension container colors in a disposable profile."""
import json, os, tempfile
from pathlib import Path
from probe_daily_defaults import launch
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

def luminance(code):
    values = [int(code[i:i+2], 16) / 255 for i in (1, 3, 5)]
    values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(v * weight for v, weight in zip(values, [.2126, .7152, .0722]))

def contrast(a, b):
    values = sorted([luminance(a), luminance(b)])
    return (values[1] + .05) / (values[0] + .05)

EXTRA = ['navy', 'teal', 'olive', 'burgundy', 'brown', 'slate', 'coral', 'apricot', 'mint', 'ice', 'lavender', 'blush', 'sand', 'charcoal']
with tempfile.TemporaryDirectory(prefix='cloakfox-colors-') as temp:
    root = Path(temp)
    profile = root / 'profile'
    profile.mkdir()
    driver = launch(profile, root / 'gecko.log', purge_caches=True)
    try:
        result = driver.execute_script("""
          const cis = ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;
          return {names:cis.containerColors, codes:cis.containerColors.map(c=>cis.getContainerColorCode(c))};
        """)
        assert set(EXTRA) <= set(result['names']), result
        assert len(set(result['codes'])) == len(result['names']) == 24, result
        for name, code in zip(result['names'], result['codes']):
            assert contrast(code, '#3d3b48') >= 4.5, (name, code, 'too dark for toolbar text')
        for color in EXTRA:
            assert driver.execute_script("""
              const cis = ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;
              const identity = cis.create('Palette test', 'circle', arguments[0]);
              return cis.getPublicIdentityFromId(identity.userContextId).color;
            """, color) == color
        tab_colors = driver.execute_script("""
          const cis=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;
          const identity=cis.create('Accent test','circle','blue');
          const tab=gBrowser.addTrustedTab('about:blank',{userContextId:identity.userContextId});
          gBrowser.selectedTab=tab;
          const s=getComputedStyle(tab.querySelector('.tab-context-line'));
          return {accent:getComputedStyle(tab).getPropertyValue('--identity-accent-color').trim(),paint:s.backgroundColor+' '+s.backgroundImage,label:cis.getContainerColorCode('blue')};
        """)
        assert tab_colors['accent'] == '#4385f5', tab_colors
        assert '67, 133, 245' in tab_colors['paint'], tab_colors
        assert tab_colors['label'] == result['codes'][result['names'].index('blue')], tab_colors
        driver.set_context('content')
        driver.get('about:preferences#containers')
        for theme in ['light', 'dark']:
            driver.execute_script("document.documentElement.style.colorScheme=arguments[0]", theme)
            for color in EXTRA:
                actual = driver.execute_script("""
                  const el=document.createElement('span');el.className='identity-color-'+arguments[0];document.body.append(el);
                  const s=getComputedStyle(el),out={icon:s.getPropertyValue('--identity-icon-color').trim(),stroke:s.getPropertyValue('--identity-stroke-color').trim()};el.remove();return out;
                """, color)
                assert actual['icon'] and actual['stroke'], (theme, color, actual)
        driver.set_context('chrome')
        addon = Path(os.environ['CLOAKFOX_BIN']).parents[1] / 'Resources/distribution/extensions/@testpilot-containers.xpi'
        driver.install_addon(str(addon), temporary=True)
        url = driver.execute_script("return ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs').ExtensionParent.GlobalManager.getExtension('@testpilot-containers').baseURI.resolve('popup.html');")
        driver.set_context('content')
        driver.get(url)
        supported = driver.execute_async_script("browser.contextualIdentities.getSupportedColors().then(arguments[arguments.length-1]);")
        assert [c['color'] for c in supported] == result['names'], supported
        driver.execute_async_script("browser.storage.local.set({'onboarding-stage':8}).then(arguments[arguments.length-1]);")
        driver.refresh()
        wait = WebDriverWait(driver, 15)
        wait.until(lambda _: driver.execute_script("return !!document.querySelector('#identities-list tr .menu-arrow')"))
        def open_info(_):
            if driver.find_element('id', 'container-info-panel').is_displayed():
                return True
            driver.execute_script("document.querySelector('#identities-list tr .menu-arrow').click();")
            return False
        wait.until(open_info)
        driver.find_element('id', 'manage-container-link').click()
        wait.until(lambda _: driver.find_element('id', 'edit-container-panel').is_displayed())
        swatches = driver.execute_script("return [...document.querySelectorAll('[name=container-color]')].map(e=>e.value);")
        assert swatches == result['names'], swatches
        for color in EXTRA:
            assert driver.find_element('css selector', f'label[for="edit-container-panel-choose-color-{color}"]').is_displayed(), color
        layout = driver.execute_script("""
          const panel=document.getElementById('edit-container-panel');
          const del=document.getElementById('delete-container-button');
          const r=del.getBoundingClientRect(),p=panel.getBoundingClientRect();
          const swatch=color=>getComputedStyle(document.querySelector('label[for="edit-container-panel-choose-color-'+color+'"]'),'::before').fill;
          return {visible:r.height>0 && r.top>=p.top && r.bottom<=Math.min(p.bottom,innerHeight),gray:swatch('gray'),charcoal:swatch('charcoal'),blue:swatch('blue')};
        """)
        assert layout['gray'] == 'rgb(204, 133, 64)', layout
        assert layout['charcoal'] == 'rgb(183, 91, 167)', layout
        assert layout['blue'] == 'rgb(67, 133, 245)', layout
        target=driver.find_element('css selector','label[for="edit-container-panel-choose-color-coral"]')
        background=lambda:driver.execute_script('return getComputedStyle(arguments[0]).backgroundColor',target)
        normal=background()
        ActionChains(driver).move_to_element(target).perform()
        assert background()!=normal, 'Native hover feedback missing'
        target.click()
        assert driver.find_element('id','edit-container-panel-choose-color-coral').is_selected()
        ActionChains(driver).move_to_element(driver.find_element('id','container-edit-title')).perform()
        assert background()!=normal, 'Native selected feedback missing'
        driver.save_screenshot('/tmp/cloakfox-container-colors.png')
        driver.quit()
        driver = launch(profile, root / 'reused-profile.log', purge_caches=True)
        reused = driver.execute_script("""
          const cis=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;
          return {codes:cis.containerColors.map(c=>cis.getContainerColorCode(c))};
        """)
        assert reused['codes'] == result['codes'], reused
        print(json.dumps({'passed':True, 'colors':result['names'], 'themes':['light','dark'], 'profileReuse':True}))
    finally:
        driver.quit()
