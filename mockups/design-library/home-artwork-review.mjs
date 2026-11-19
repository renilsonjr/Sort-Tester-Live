const $ = selector => document.querySelector(selector);
function update() {
 const guest = $('#visitor').value === 'guest';
 $('#campaign').hidden = $('#visual').value !== 'art';
 $('#home-eyebrow').textContent = guest ? 'Guest practice' : 'Welcome back, parcel_fox';
 document.querySelectorAll('[data-member]').forEach(el => el.hidden = guest);
 document.querySelectorAll('[data-guest]').forEach(el => el.hidden = !guest);
 $('.top-login').hidden = !guest;
 $('#member-tag').hidden = guest;
 $('.nav').classList.toggle('guest', guest);
 $('#launch-callout').hidden = $('#season').value !== 'live';
 $('#demo-status').hidden = true;
}
for (const id of ['visual', 'visitor', 'season']) $(`#${id}`).addEventListener('change', update);
document.addEventListener('click', event => {
 const button = event.target.closest('[data-go], [data-demo]');
 if (!button) return;
 $('#demo-status').textContent = `${button.dataset.demo || button.querySelector('strong')?.textContent || 'Navigation'} selected. This page previews the home only. Use the design library to review the other screens.`;
 $('#demo-status').hidden = false;
});
update();
