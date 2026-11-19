import {screens,filterScreens} from './catalog.mjs';
import {BELT_STYLE} from '../../src/belts.js';

const $=selector=>document.querySelector(selector);
const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statusNames={existing:'Existing flow',approved:'Approved path',concept:'Concept'};
const go=(label,id,variant='primary')=>`<button type="button" class="${variant} full" data-go="${id}">${label}</button>`;
const choice=(n,title,text,id)=>`<button type="button" class="choice-card" data-go="${id}"><span class="choice-number">${n}</span><span><strong>${title}</strong><small>${text}</small></span><span class="choice-arrow" aria-hidden="true">→</span></button>`;
const chip=belt=>`<span class="belt-chip" style="background:${BELT_STYLE[belt].bg};color:${BELT_STYLE[belt].fg}">${belt}</span>`;
const alert=(title,text,type='')=>`<div class="alert ${type}"><strong>${title}</strong>${text}</div>`;
const route=(state,code,belt)=>`<div class="route-row"><div><strong>${state}</strong><small>${code}</small></div>${chip(belt)}</div>`;
const field=(label,placeholder,id='sample-field',extra='')=>`<label class="field-demo" for="${id}">${label}<input id="${id}" type="text" autocomplete="off" placeholder="${placeholder}" ${extra}></label>`;
const announcement=()=>alert('Sort-change announcement','Sample announcement area. Follow the current worksite chart.');
const demoButton=(text,kind='')=>`<button type="button" class="${kind}" data-demo="Sample action — no app data changed.">${text}</button>`;
const section=(title,content)=>`<div class="panel-block"><h3>${title}</h3>${content}</div>`;
const spec=(title,description,body)=>`<article class="spec"><h3>${title}</h3><p class="caption">${description}</p>${body}</article>`;

$('#foundation-specimens').innerHTML=section('Surface & action colors',`<div class="token-grid">${[['Dark brown','--brand','#38261b'],['Action gold','--accent','#f4bd38'],['Warm white','--surface','#fffdf8'],['Page','--page','#f7f3ec'],['Body text','--ink','#35271e'],['Focus blue','--focus','#175e94']].map(([name,token,color])=>`<div class="token"><div class="token-swatch" style="background:${color}"></div><strong>${name}</strong><code>${token} · ${color}</code></div>`).join('')}</div>`)+section('Routing colors · preserved',`<div class="spec-row">${Object.keys(BELT_STYLE).map(chip).join('')}</div><p class="caption">Imported from the app’s current belt palette. Labels remain visible; route meaning never depends on color alone.</p>`)+`<div class="spec-grid">${spec('Nunito, locally hosted','One type family, clear visual hierarchy.',`<div class="type-hero">Practice the chart.</div><h3 style="margin-top:20px">Know the next step.</h3><p>Choose a service, study a route, and practice at your pace.</p><small>Small copy stays readable. Button labels use a strong weight.</small>`)}${spec('Spacing & corners','A small scale keeps the interface consistent.',`<div class="space-row">${[4,8,12,16,24,32].map(n=>`<span><i style="height:${n}px"></i>${n}px</span>`).join('')}</div><div class="spec-row"><div class="token" style="border-radius:12px">12 · controls</div><div class="token" style="border-radius:18px">18 · cards</div><div class="token" style="border-radius:26px">26 · groups</div></div><p class="caption">Main actions ≥48px high. Phone layouts start at 320px wide.</p>`)}</div>`;

$('#component-specimens').innerHTML=`<div class="spec-grid">${[
 spec('Actions','One gold primary action; quiet alternatives.',`<div class="spec-row">${demoButton('Continue','primary')}${demoButton('Log in','button-secondary')}${demoButton('Back')}${demoButton('Learn more','button-text')}${demoButton('Clear log','button-danger')}</div>`),
 spec('Button states','Hover, keyboard focus, pressed, disabled and busy.',`<div class="spec-row"><button class="primary button-hover" data-demo="Hover specimen">Hover</button><button class="primary button-focus" data-demo="Focus specimen">Focus</button><button class="primary button-pressed" data-demo="Pressed specimen">Pressed</button><button disabled>Unavailable</button><button id="loading-demo" class="primary">Try loading</button></div><p class="caption">The blue outline identifies keyboard focus. Disabled controls remain readable.</p>`),
 spec('Fields & validation','Visible labels, helper copy and specific feedback.',`${field('Optional practice name','e.g. Sample sorter','component-name')}<label class="field-demo" for="component-id">Login ID<input id="component-id" placeholder="Enter your login ID" aria-invalid="true" aria-describedby="component-error"><small id="component-error" class="error-text">Example error: enter the complete login ID.</small></label><label class="field-demo" for="readonly-id">Saved identifier<input id="readonly-id" readonly value="DEMO — NOT A REAL LOGIN ID"></label><label class="check-row"><input id="component-saved" type="checkbox"> I saved my login ID</label><button id="component-continue" disabled style="margin-top:12px">Continue</button>`),
 spec('Language & service selection','Selected state uses text, color and a pressed attribute.',`<div class="segmented" data-segments aria-label="Sample language" role="group"><button aria-pressed="true">EN</button><button aria-pressed="false">ES</button></div><div class="segmented" data-segments aria-label="Sample service" role="group" style="margin-top:16px"><button aria-pressed="true">Ground</button><button aria-pressed="false">2 Day Air</button><button aria-pressed="false">3 Day Select</button></div>`),
 spec('Choice & deck cards','The whole card is the action.',`${choice('01','Know the chart','Browse services and exceptions.','study')}<button class="deck-card" data-go="picker"><strong>01 · Ground basics</strong><small>One service, a focused practice session.</small><small>Practice deck · 15s each</small></button><button class="deck-card" disabled><strong>Unavailable deck</strong><small>Not checked against the chart yet.</small></button>`),
 spec('Navigation','Approved guest and member paths.',`<p class="caption">Guest</p><div class="sample-tabs"><button data-go="guest-home" aria-current="page">Home</button><button data-go="practice">Practice</button></div><p class="caption">Member</p><div class="sample-tabs"><button data-go="home" aria-current="page">Home</button><button data-go="practice">Practice</button><button data-go="ranked">Ranked</button><button data-go="profile">Profile</button></div>`),
 spec('Belt answers & route rows','Original colors with clear text labels.',`<div class="spec-row">${['YELLOW','PINK','ORANGE','GOLD'].map(b=>`<button class="belt-button" style="background:${BELT_STYLE[b].bg};color:${BELT_STYLE[b].fg}" data-demo="${b} selected in this specimen.">${b}</button>`).join('')}</div>${route('Sample state','000–009','GOLD')}<p class="caption">Fictional route for appearance review.</p>`),
 spec('Timers & progress','Normal and urgent states have visible numbers.',`<div class="spec-row"><div class="timer" aria-label="15 seconds remaining">15</div><div class="timer urgent" aria-label="3 seconds remaining">3</div><span>Question 4 of 15</span></div><div class="progress-track" role="progressbar" aria-label="Example quiz progress" aria-valuemin="0" aria-valuemax="15" aria-valuenow="10"><div class="progress-fill"></div></div>`),
 spec('Feedback & notices','Meaning is expressed in words as well as color.',`${alert('Correct!','You picked the right belt.','success')}${alert('Review this route','Your choice and the expected belt appear together.','error')}${alert('Results not saved','Example warning for unavailable browser storage.')}${alert('Connection unavailable','Example service message. Try again when connected.','info')}`),
 spec('Results & history','A clear score with a path into review.',`<div class="metric-grid"><div class="metric"><strong>12/15</strong><small>Sample score</small></div><div class="metric"><strong>02:18</strong><small>Sample time</small></div></div><div class="route-row"><div><strong>Sample sorter</strong><small>Ground practice · Fictional attempt</small></div><strong>12/15</strong></div>`),
 spec('Empty & loading states','Explain what can happen next.',`<div class="empty"><strong>Nothing recorded yet.</strong><p>Finish a practice quiz to see your results here.</p>${demoButton('Start practice','primary')}</div><div class="spec-row"><span class="is-loading"><span class="spinner" aria-hidden="true"></span>Loading sample content…</span></div>`),
 spec('Disclosure & confirmation','Keep detail optional and destructive actions deliberate.',`<details><summary>Review missed routes</summary><p>A missed route would show your choice, the expected belt and an explanation.</p></details><button id="open-dialog" class="button-danger" style="margin-top:18px">Preview clear-log dialog</button>`)
].join('')}</div>`;

const quizHead=()=>`<div class="quiz-head"><span>Practice · Question 4 of 15</span><div class="timer" aria-label="Static sample: 15 seconds">15</div></div>`;
const quizRoute=()=>`<div class="quiz-service">Ground · SAMPLE STATE</div><div class="quiz-code">000–009</div><p class="caption" style="text-align:center">Fictional route · Visual example only</p>`;
const nav=(member,active)=>`<nav class="sample-tabs phone-nav" aria-label="Screen preview navigation">${(member?[['home','Home'],['practice','Practice'],['ranked','Ranked'],['profile','Profile']]:[['guest-home','Home'],['practice','Practice']]).map(([id,label])=>`<button type="button" data-go="${id}"${id===active?' aria-current="page"':''}>${label}</button>`).join('')}</nav>`;
let member=false;
const screenTemplates={
 entry:()=>`${announcement()}<h4>How do you want to use Sort Lab?</h4><div class="spec" style="padding:18px"><div class="eyebrow">Ranked</div><h5>Play for points</h5><p>Log in to enter Ranked.</p>${go('Log in','login')}</div><div class="spec" style="padding:18px;margin-top:14px"><div class="eyebrow">Practice</div><h5>Study and practice</h5><p>Explore the chart and take practice quizzes.</p>${go('Continue as guest','guest-home','')}</div>`,
 login:()=>`<h4>Welcome back.</h4><p>Enter your login ID.</p>${field('Login ID','Use a fictional value here','preview-login')}<p class="caption">Visual example only. Never enter a real login ID in this library.</p>${go('Log in · Demo','home')}${go('Create account','register','')}${go('Lost your login ID?','lost','button-text')}${go('Back','entry','button-text')}`,
 register:()=>`<h4>Create account</h4><p>Choose the name other players will see.</p>${field('Username','sample_sorter','preview-username')}<p class="caption">No account will be created.</p>${go('Create account · Demo','save-id')}${go('Cancel','login','')}`,
 'save-id':()=>`<h4>Save your login ID.</h4>${alert('Shown once','Keep your ID somewhere safe. This value is a nonfunctional example.')}${field('Your login ID','DEMO — NOT A REAL ID','preview-generated','readonly value="DEMO — NOT A REAL ID"')}<label class="check-row"><input type="checkbox" id="preview-saved"> I saved my login ID</label><button class="primary full" id="preview-saved-next" data-go="home" disabled>Continue</button>`,
 lost:()=>`<h4>Lost your login ID?</h4>${alert('Ask the owner in person','Talk to the Sort Lab owner at work to verify your identity and restore access.','info')}${go('Back to log in','login','')}`,
 'guest-home':()=>`${announcement()}<h4>Study the chart.<br>Build confidence.</h4>${choice('01','Know the chart','Browse services and exceptions.','study')}${choice('02','Try a quiz','Practice at your own pace.','name')}${go('Log in','login','')}`,
 home:()=>`${announcement()}<h4>Ready for your next step?</h4>${choice('01','Practice','Study the chart or try a quiz.','practice')}${choice('02','Ranked','Play for points this season.','ranked')}`,
 practice:()=>`<div class="eyebrow">Practice</div><h4>Study and practice.</h4>${choice('01','Know the chart','Explore services and exceptions.','study')}${choice('02','Try a quiz','Pick a test and build confidence.','name')}${go('Shift log','log','button-text')}`,
 study:()=>`<div class="eyebrow">Study guide</div><h4>Know the chart.</h4><div class="segmented" role="group" aria-label="Preview services" data-segments><button aria-pressed="true">Ground</button><button aria-pressed="false">2 Day Air</button></div><label class="field-demo" for="preview-route-search">Find a state or number<input type="search" id="preview-route-search" placeholder="Try Sample or 000"></label><p class="caption">Illustrative rows only; not an operational chart.</p><div id="preview-route-rows">${route('Sample state','000–009','GOLD')}${route('Example state','010–019','ORANGE')}${route('Sample exception','000 1','PURPLE')}</div><p id="preview-no-routes" hidden>No matching example routes.</p>`,
 name:()=>`<h4>Quiz yourself.</h4>${field('Name or ID (optional)','e.g. Sample sorter','preview-name')}<p class="caption">Practice results stay on your device in the actual app. This preview saves nothing.</p>${go('Pick a test','picker')}${go('Back to home',member?'home':'guest-home','')}`,
 picker:()=>`<h4>Pick a test.</h4><button class="deck-card" data-go="question"><strong>01 · Ground basics</strong><small>Build confidence with one service.</small><small>Sample deck · 15s each</small></button><button class="deck-card" data-go="question"><strong>02 · Mixed practice</strong><small>Practice different services together.</small><small>Sample deck · 15s each</small></button><button class="deck-card" disabled><strong>Unavailable deck</strong><small>Not checked against the chart yet.</small></button>${go('Edit name','name','button-text')}`,
 question:()=>`${quizHead()}${quizRoute()}<h5 style="text-align:center">Where does this go?</h5><div class="answer-grid">${['YELLOW','PINK','ORANGE','GOLD'].map(b=>`<button class="belt-button" data-go="${b==='GOLD'?'correct':'incorrect'}" style="background:${BELT_STYLE[b].bg};color:${BELT_STYLE[b].fg}">${b}</button>`).join('')}</div>${go('Preview time expired','timeout','button-text')}${go('Cancel','stop','')}`,
 correct:()=>`<h4>Correct!</h4>${quizRoute()}${route('Your choice','', 'GOLD')}${route('Correct belt','', 'GOLD')}${alert('Nice work','An explanation appears here.','success')}<p class="caption">In the app, the next question starts automatically. This review stays still.</p>${go('Preview next question','question')}`,
 incorrect:()=>`<h4>Review this route.</h4>${quizRoute()}${route('Your choice','','ORANGE')}${route('Correct belt','','GOLD')}${alert('Keep practicing','Review the expected belt and the explanation before continuing.','error')}${go('Continue','question')}`,
 timeout:()=>`<h4>Out of time.</h4><div class="timer urgent" aria-label="0 seconds remaining">0</div>${quizRoute()}<div class="route-row"><strong>Your choice</strong><span>No choice</span></div>${route('Correct belt','','GOLD')}<p>The app explains the route here.</p>${go('Continue','question')}`,
 stop:()=>`<h4>Test stopped.</h4><p>Nothing is saved until a test is finished, so leaving now records nothing.</p>${go('Keep going','question')}${go('Pick another test','picker','')}${go('Main page',member?'home':'guest-home','')}`,
 results:()=>`<h4>Your practice results.</h4><div class="metric-grid"><div class="metric"><strong>12/15</strong><small>Sample score</small></div><div class="metric"><strong>02:18</strong><small>Sample time</small></div></div><p>Sample sorter · Ground practice</p><h5>Missed routes</h5><details><summary>Sample state · 000–009</summary><p>Your choice: ORANGE → Expected: GOLD</p><p>Explanation of this fictional example.</p></details>${go('Back to main page',member?'home':'guest-home')}${go('Shift log','log','')}`,
 log:()=>`<h4>Shift log.</h4><p class="caption">Fictional examples of device-local history.</p><div id="sample-log-entries">${['12/15','14/15'].map(score=>`<div class="route-row"><div><strong>Sample sorter</strong><small>Ground practice · Sample date</small></div><strong>${score}</strong></div>`).join('')}</div>${go('Main page',member?'home':'guest-home')}<button class="full" data-demo="Export appearance only — no file is generated.">Export to Excel</button><button class="full button-danger" data-dialog>Clear log</button>`,
 'log-empty':()=>`<h4>Shift log.</h4><div class="empty"><strong>Nothing recorded yet.</strong><p>Your completed practice results appear here.</p>${go('Start practice','name')}</div>${go('Main page',member?'home':'guest-home','')}`,
 ranked:()=>`<div class="concept-note">Concept · Navigation approved; content not finalized.</div><h4>Pre-Season</h4><p>Ranked screen placeholder.</p><img class="rank-image" src="badges/iron-concept-v1.png" alt="Iron badge concept"><p class="caption">Badge placement study only.</p><button class="primary full" data-demo="Ranked gameplay is outside this visual preview.">Start Ranked quiz</button>${choice('#','Leaderboard','View the member-only path.','leaderboard')}`,
 leaderboard:()=>`<div class="concept-note">Concept · Layout and ranking details not finalized.</div><h4>Leaderboard</h4><div class="empty"><strong>Standings preview</strong><p>Final standings content belongs to the leaderboard design. No real players or rankings are shown here.</p></div>${go('Back to Ranked','ranked','')}`,
 profile:()=>`<div class="concept-note">Concept · Identity and navigation placement only.</div><h4>sample_sorter</h4><p class="caption">Fictional member · #0000</p>${choice('?','Support','Your tickets.','tickets')}${go('Log out · Demo','entry','')}`,
 tickets:()=>`<div class="concept-note">Concept · Ticket form and list still to be designed.</div><h4>Tickets</h4><p>Support lives here.</p><button class="primary full" data-demo="The ticket form is not designed yet. No ticket will be created.">Create ticket</button>${go('Back to Profile','profile','')}`,
};

let selected='entry';
function listScreens(){
 const filtered=filterScreens($('#screen-search').value,$('#screen-filter').value);
 $('#screen-count').textContent=`${filtered.length} of ${screens.length} screens`;
 $('#screen-list').innerHTML=filtered.map(s=>`<button type="button" data-screen="${s.id}" aria-pressed="${selected===s.id}"><span>${s.title}</span><small>${statusNames[s.status]}</small></button>`).join('')||'<p class="caption">No matching screens. Try another search.</p>';
}
function showScreen(id,focus=false){
 const s=screens.find(s=>s.id===id);if(!s)return;
 selected=id;
 if(['home','ranked','leaderboard','profile','tickets'].includes(id))member=true;
 if(['entry','guest-home'].includes(id))member=false;
 $('#screen-meta').innerHTML=`<div class="eyebrow">${statusNames[s.status]} · Refreshed specimen</div><h3 tabindex="-1" id="selected-screen-title">${s.title}</h3><p>${s.description}</p><div class="source-link">Source: ${escape(s.source)}</div>`;
 $('#screen-content').innerHTML=screenTemplates[id]();
 $('#screen-content').classList.remove('screen-content-enter');
 void $('#screen-content').offsetWidth;
 $('#screen-content').classList.add('screen-content-enter');
 const auth=['entry','login','register','save-id','lost'];
 const quiz=['question','correct','incorrect','timeout','stop','results','log','log-empty','name','picker'];
 $('#screen-navigation').innerHTML=auth.includes(id)||quiz.includes(id)?'':nav(member,['study','practice'].includes(id)?'practice':['ranked','leaderboard'].includes(id)?'ranked':['profile','tickets'].includes(id)?'profile':id);
 listScreens();
 if(focus)$('#selected-screen-title').focus({preventScroll:true});
}
async function activate(name,focus=false){
 if(!['foundations','components','screens','motion'].includes(name))name='foundations';
 for(const panel of document.querySelectorAll('.page-section'))panel.hidden=panel.id!==name;
 for(const link of document.querySelectorAll('.library-nav a')){if(link.hash===`#${name}`)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}
 history.replaceState(null,'',`#${name}`);
 if(focus)$(`#${name}-title`).focus({preventScroll:true});
}
let toastTimeout;
function toast(text){clearTimeout(toastTimeout);$('#toast').textContent=text;$('#toast').hidden=false;toastTimeout=setTimeout(()=>{$('#toast').hidden=true;},3500);}
let dialogTrigger;
function openDialog(trigger){dialogTrigger=trigger;$('#review-dialog').showModal();}
$('#dialog-cancel').addEventListener('click',()=>$('#review-dialog').close());
$('#dialog-confirm').addEventListener('click',()=>{$('#review-dialog').close();toast('Sample confirmation complete. No real results were deleted.');});
$('#review-dialog').addEventListener('close',()=>{if(dialogTrigger?.isConnected)dialogTrigger.focus();});
$('#screen-search').addEventListener('input',listScreens);
$('#screen-filter').addEventListener('change',listScreens);
let loadingTimeout;
document.addEventListener('click',event=>{
 const target=event.target.closest('button,a');if(!target)return;
 if(target.closest('.library-nav')){event.preventDefault();activate(target.hash.slice(1),true);return;}
 if(target.dataset.screen){showScreen(target.dataset.screen,true);return;}
 if(target.dataset.go){activate('screens');showScreen(target.dataset.go,true);return;}
 if(target.dataset.demo){toast(target.dataset.demo);return;}
 if(target.hasAttribute('data-dialog')||target.id==='open-dialog'){openDialog(target);return;}
 if(target.closest('[data-segments]')){for(const b of target.parentElement.querySelectorAll('button'))b.setAttribute('aria-pressed',String(b===target));return;}
 if(target.hasAttribute('data-preview-language')){toast('This design review uses English copy. The current app supports English and Spanish.');return;}
 if(target.id==='loading-demo'){
  clearTimeout(loadingTimeout);target.disabled=true;target.classList.add('is-loading');target.setAttribute('aria-busy','true');target.innerHTML='<span class="spinner" aria-hidden="true"></span>Loading…';
  loadingTimeout=setTimeout(()=>{target.disabled=false;target.classList.remove('is-loading');target.removeAttribute('aria-busy');target.textContent='Try loading';toast('Sample action finished.');},1200);
 }
 if(target.dataset.replay){const item=document.getElementById(target.dataset.replay);item.classList.remove('run');void item.offsetWidth;item.classList.add('run');}
});
document.addEventListener('change',event=>{
 if(event.target.id==='component-saved')$('#component-continue').disabled=!event.target.checked;
 if(event.target.id==='preview-saved')$('#preview-saved-next').disabled=!event.target.checked;
});
$('#component-continue').addEventListener('click',()=>toast('Saved-ID confirmation specimen complete.'));
document.addEventListener('input',event=>{
 if(event.target.id!=='preview-route-search')return;
 const term=event.target.value.trim().toLowerCase();let count=0;
 for(const row of $('#preview-route-rows').children){row.hidden=!row.textContent.toLowerCase().includes(term);if(!row.hidden)count++;}
 $('#preview-no-routes').hidden=count>0;
});
const motionExamples=[['enter','Screen entrance','240ms · Fade in and move 8px.','<div class="motion-object motion-enter" id="demo-enter">Next screen</div>'],['feedback','Answer feedback','480ms · A small, one-time emphasis.','<div class="motion-object motion-feedback" id="demo-feedback">Correct!</div>'],['toast','Status notice','300ms · Enter without taking keyboard focus.','<div class="motion-object motion-toast" id="demo-toast">Sample result saved</div>'],['progress','Timer progress','1.8s demo · Actual quiz timing stays unchanged.','<div class="progress-track" style="width:100%"><div class="progress-fill motion-progress" id="demo-progress"></div></div>'],['badge','Badge reveal','700ms · A restrained one-time reveal.','<img class="motion-badge" id="demo-badge" src="badges/gold-concept-v1.png" alt="Gold badge reveal" style="width:110px;height:110px;object-fit:contain">']];
$('#motion-specimens').innerHTML=motionExamples.map(([id,title,description,content])=>spec(title,description,`<div class="motion-demo-stage">${content}</div><button data-replay="demo-${id}">Replay ${title.toLowerCase()}</button>`)).join('');
const reduce=matchMedia('(prefers-reduced-motion: reduce)');
$('#ui-still').checked=reduce.matches;
function applyMotion(){document.documentElement.dataset.still=String($('#ui-still').checked);}
$('#ui-still').addEventListener('change',applyMotion);
reduce.addEventListener('change',event=>{$('#ui-still').checked=event.matches;applyMotion();});
applyMotion();showScreen('entry');activate(location.hash.slice(1));
window.addEventListener('hashchange',()=>activate(location.hash.slice(1),true));
