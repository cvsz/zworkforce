/*
 * Z.A.R.V.I.S. agent HUD — adapted from interaction/design patterns in
 * RubenM1990/APEX-UI (MIT). See docs/APEX-UI-ATTRIBUTION.md.
 *
 * Security boundary: this file reads already-rendered dashboard state only.
 * It never handles credentials, voice tickets, approvals, or provider secrets.
 */
(function attachZarvisAgentHud(root){
  'use strict';

  const card = document.getElementById('zarvisCard');
  const web = document.getElementById('zarvisReasoningWeb');
  const overview = document.getElementById('zarvisAgentOverview');
  const count = document.getElementById('zarvisAgentCount');
  const runtimeState = document.getElementById('zarvisHudState');
  const source = document.getElementById('agentCards');
  if (!card || !web || !overview || !count || !runtimeState || !source) return;

  const NS = 'http://www.w3.org/2000/svg';
  const MAX_NODES = 12;

  function text(value){ return String(value || '').replace(/\s+/g, ' ').trim(); }
  function short(value, max=10){ const v=text(value); return v.length > max ? `${v.slice(0,max-1)}…` : v; }

  function readAgents(){
    return Array.from(source.querySelectorAll('.agent')).slice(0, MAX_NODES).map((el, index) => ({
      index,
      name: text(el.querySelector('h3')?.textContent) || `Agent ${index + 1}`,
      description: text(el.querySelector('p')?.textContent),
      meta: Array.from(el.querySelectorAll('.agent-meta span')).map(x => text(x.textContent)).filter(Boolean),
    }));
  }

  function svgEl(name, attrs={}){
    const el=document.createElementNS(NS,name);
    Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,String(v)));
    return el;
  }

  function setOverview(agent){
    if(!agent){
      overview.hidden=true;
      overview.replaceChildren();
      return;
    }
    const strong=document.createElement('strong');
    strong.textContent=agent.name;
    const body=document.createElement('div');
    body.textContent=agent.description || 'Registered zWorkforce agent.';
    overview.replaceChildren(strong, body);
    if(agent.meta.length){
      const meta=document.createElement('span');
      meta.textContent=agent.meta.join(' · ');
      overview.append(meta);
    }
    overview.hidden=false;
  }

  function render(){
    const agents=readAgents();
    count.textContent=`${agents.length} agents`;
    web.replaceChildren();

    const svg=svgEl('svg',{viewBox:'0 0 100 100','aria-hidden':'true',focusable:'false'});
    svg.append(svgEl('circle',{cx:50,cy:50,r:37,class:'hud-orbit'}));
    svg.append(svgEl('circle',{cx:50,cy:50,r:46,class:'hud-orbit'}));

    if(!agents.length){
      web.append(svg);
      setOverview(null);
      return;
    }

    agents.forEach((agent,index)=>{
      const angle=(-Math.PI/2)+(Math.PI*2*index/agents.length);
      const radius=index%2===0?43:36;
      const x=50+Math.cos(angle)*radius;
      const y=50+Math.sin(angle)*radius;

      const link=svgEl('line',{x1:50,y1:50,x2:x,y2:y,class:`hud-link${index<3?' active':''}`});
      svg.append(link);

      const group=svgEl('g',{class:'hud-node',transform:`translate(${x} ${y})`,tabindex:'0',role:'button','aria-label':`Show ${agent.name} details`});
      group.dataset.index=String(index);
      group.append(svgEl('circle',{r:5.6}));
      const label=svgEl('text',{x:0,y:0});
      label.textContent=short(agent.name,9);
      group.append(label);

      const select=()=>{
        svg.querySelectorAll('.hud-node').forEach(n=>n.dataset.selected='false');
        group.dataset.selected='true';
        setOverview(agent);
      };
      group.addEventListener('click',select);
      group.addEventListener('keydown',(event)=>{
        if(event.key==='Enter'||event.key===' '){event.preventDefault();select();}
        if(event.key==='Escape'){setOverview(null);group.dataset.selected='false';}
      });
      svg.append(group);
    });
    web.append(svg);
  }

  function syncVoiceState(){
    const current=card.dataset.voiceState || 'idle';
    runtimeState.textContent=current.replaceAll('_',' ');
  }

  const agentObserver=new MutationObserver(render);
  agentObserver.observe(source,{childList:true,subtree:true,characterData:true});

  const stateObserver=new MutationObserver(syncVoiceState);
  stateObserver.observe(card,{attributes:true,attributeFilter:['data-voice-state']});

  render();
  syncVoiceState();

  root.addEventListener('pagehide',()=>{
    agentObserver.disconnect();
    stateObserver.disconnect();
  },{once:true});
})(window);
