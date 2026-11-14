import {BELT_STYLE} from '../../src/belts.js';
const $=s=>document.querySelector(s);
let scene='question';
const avatarStates={question:'thinking',correct:'correct',incorrect:'incorrect',timeout:'incorrect',results:'idle'};
const explanations={question:'Thinking enquanto você escolhe o belt.',correct:'Correct: salto e comemoração, depois volta à expressão neutra.',incorrect:'Incorrect: breve reação de oops, depois se recupera.',timeout:'Tempo esgotado: reação breve de oops, com mensagem específica de tempo.',results:'Idle: o personagem acompanha o resumo sem comemorar uma pontuação arbitrária.'};
function sendAvatar(extra={}){$('#avatar').contentWindow?.postMessage({type:'quiz-avatar',state:avatarStates[scene],still:$('#still').checked,...extra},location.origin);}
const chip=b=>`<span class="chip" style="background:${BELT_STYLE[b].bg};color:${BELT_STYLE[b].fg}">${b}</span>`;
const route=()=>'<div class="route-service">Ground · SAMPLE STATE</div><div class="route-code">000–009</div><div class="sample-label">Fictional route · Appearance review only</div>';
function show(next,focus=true){
 if(!Object.hasOwn(avatarStates,next))return;scene=next;
 for(const b of document.querySelectorAll('[data-scene]'))b.setAttribute('aria-pressed',String(b.dataset.scene===scene));
 $('#explanation').textContent=explanations[scene];$('#timer').classList.toggle('expired',scene==='timeout');$('#timer').textContent=scene==='timeout'?'0':'15';$('#timer').hidden=scene!=='question'&&scene!=='timeout';$('#timer').setAttribute('aria-label',scene==='timeout'?'Exemplo estático: 0 segundos':'Exemplo estático: 15 segundos');
 $('#step').textContent=scene==='results'?'Practice complete':'Question 4 of 15';$('#progress-fill').style.width=scene==='results'?'100%':'27%';
 if(scene==='question')$('#quiz-content').innerHTML=`${route()}<h2 class="question" tabindex="-1">Where does this go?</h2><div class="answers">${['YELLOW','PINK','ORANGE','GOLD'].map(b=>`<button data-answer="${b}" style="background:${BELT_STYLE[b].bg};color:${BELT_STYLE[b].fg}">${b}</button>`).join('')}</div>`;
 else if(scene==='results')$('#quiz-content').innerHTML='<h2 class="verdict" tabindex="-1">Practice complete.</h2><div class="metrics"><div class="metric"><strong>12/15</strong><small>Sample score</small></div><div class="metric"><strong>02:18</strong><small>Sample time</small></div></div><p class="results-note">Sample sorter · Ground practice<br>Review your missed routes before the next attempt.</p><button class="primary full" data-next>Practice again</button>';
 else {const good=scene==='correct';$('#quiz-content').innerHTML=`<h2 class="verdict ${good?'success':'error'}" tabindex="-1">${good?'Correct!':scene==='timeout'?'Out of time.':'Review this route.'}</h2>${route()}<div class="answer-row"><span>Your choice</span>${scene==='timeout'?'<strong>No choice</strong>':chip(good?'GOLD':'ORANGE')}</div><div class="answer-row"><span>Correct belt</span>${chip('GOLD')}</div><p class="why">${good?'Nice work.':scene==='timeout'?'The time ended before a choice was made.':'Keep practicing.'} This fictional example illustrates where the route explanation will appear.</p><button class="primary full" data-next>Continue</button>`;}
 sendAvatar();if(focus)$('#quiz-content h2').focus({preventScroll:true});
}
$('#avatar').addEventListener('load',()=>sendAvatar());
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.scene)show(b.dataset.scene);if(b.dataset.answer)show(b.dataset.answer==='GOLD'?'correct':'incorrect');if(b.hasAttribute('data-next'))show('question');});
const media=matchMedia('(prefers-reduced-motion: reduce)');$('#still').checked=media.matches;$('#still').onchange=()=>sendAvatar();media.addEventListener('change',e=>{$('#still').checked=e.matches;sendAvatar();});$('#replay').onclick=()=>sendAvatar();
$('#cancel').onclick=()=>{sendAvatar({paused:true});$('#stop-dialog').showModal();};$('#keep-going').onclick=()=>$('#stop-dialog').close();$('#restart').onclick=()=>{$('#stop-dialog').close();show('question');};$('#stop-dialog').addEventListener('close',()=>{sendAvatar({paused:false});$('#cancel').focus();});
show('question',false);
