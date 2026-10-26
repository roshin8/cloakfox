/* Compare configured identity traits, never random seeds or identity tags.
 * This heuristic measures overlap, not the probability of tracking/linkage. */
const groups = [
  {label:"Browser identity",weight:20,keys:["navigator.userAgent","navigator.platform"]},
  {label:"Graphics",weight:30,keys:["webGl:vendor","webGl:renderer"]},
  {label:"Screen",weight:25,keys:["screen.width","screen.height","window.devicePixelRatio"]},
  {label:"CPU cores",weight:15,keys:["navigator.hardwareConcurrency"]},
  {label:"Fonts",weight:10,keys:["fonts"]},
];
function canonical(value) {
  return JSON.stringify(Array.isArray(value) ? [...value].sort() : value);
}
export function comparePersonaTraits(candidate, other) {
  let score=0, compared=0;
  const shared=[], sharedFields=[];
  for(const group of groups) {
    if(!group.keys.every(key=>candidate?.[key] !== undefined && other?.[key] !== undefined && candidate[key] !== null && other[key] !== null && candidate[key] !== "" && other[key] !== "")) continue;
    compared+=group.weight;
    for (const key of group.keys) {
      if (canonical(candidate[key]) === canonical(other[key])) sharedFields.push({key,value:candidate[key]});
    }
    if(group.keys.every(key=>canonical(candidate[key])===canonical(other[key]))) {
      score+=group.weight;shared.push(group.label);
    }
  }
  return {score,compared,shared,sharedFields,tooClose:compared>=90 && score>=85};
}
export function findSimilarPersonas(candidate, containers, currentId) {
  return containers.filter(item=>item.ucid!==currentId && item.cfg)
    .map(item=>({ucid:item.ucid,name:item.name,...comparePersonaTraits(candidate,item.cfg)}))
    .filter(item=>item.tooClose).sort((a,b)=>b.score-a.score || a.ucid-b.ucid);
}
