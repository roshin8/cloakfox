"""Preserve UI geometry on failed real WebDriver clicks without bypassing them."""
import json

_GEOMETRY = """const el=arguments[0],r=el.getBoundingClientRect();
const ancestors=[];for(let n=el;n;n=n.parentElement){const s=getComputedStyle(n);
ancestors.push({tag:n.tagName,id:n.id,hidden:n.hidden,open:n.open,
display:s.display,visibility:s.visibility,overflow:s.overflow})}
return {hash:location.hash,rect:r.toJSON(),viewport:[innerWidth,innerHeight],
scroll:[scrollX,scrollY],disabled:el.disabled,busy:el.getAttribute('aria-busy'),
status:document.getElementById('cfx-identity-status')?.textContent,
top:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.id,ancestors};"""


def click_with_evidence(driver, element, report_path, name):
    try:
        element.click()
    except Exception:
        evidence = {}
        try:
            evidence['geometry'] = driver.execute_script(_GEOMETRY, element)
        except Exception as error:
            evidence['geometryError'] = str(error)
        try:
            driver.save_screenshot(str(report_path / (name + '.png')))
        except Exception as error:
            evidence['screenshotError'] = str(error)
        try:
            (report_path / (name + '.json')).write_text(json.dumps(evidence, indent=2))
        except Exception as error:
            print('Could not preserve click evidence:', error, flush=True)
        raise
