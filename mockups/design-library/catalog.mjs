// Inventory source/status describes the owning flow, not production approval of this refresh.
export const screens = [
 ['entry','Public entry','approved','mockups/entry-navigation.html','Announcements and the two explained entry paths.'],
 ['login','Log in','existing','src/auth.js','One login ID field; no password or email.'],
 ['register','Create account','existing','src/auth.js','Choose a username.'],
 ['save-id','Save login ID','existing','src/auth.js','One-time identifier display and saved confirmation.'],
 ['lost','Lost login ID','approved','mockups/entry-navigation.html','In-person owner recovery; no email form.'],
 ['guest-home','Guest home','approved','mockups/entry-navigation.html','Two navigation tabs and a header login action.'],
 ['home','Member home','approved','mockups/entry-navigation.html','Announcements, Practice and Ranked paths.'],
 ['practice','Practice hub','approved','mockups/entry-navigation.html','Study and quiz inside one Practice destination.'],
 ['study','Study chart','existing','src/app.js · showStudy','Service selection, search, routes and exceptions.'],
 ['name','Optional practice name','existing','src/app.js · showNameEntry','Device-local optional name before selecting a test.'],
 ['picker','Pick a test','existing','src/app.js · showDeckPicker','Deck cards, metadata and an unavailable deck.'],
 ['question','Practice question','existing','src/app.js · showCard','Question, timer and belt answer buttons.'],
 ['correct','Correct answer','existing','src/app.js · showFeedback','Positive feedback with an automatic advance message.'],
 ['incorrect','Incorrect answer','existing','src/app.js · showFeedback','Compare choice and correct belt; continue manually.'],
 ['timeout','Time expired','existing','src/app.js · showFeedback','No choice and explanatory feedback.'],
 ['stop','Stop confirmation','existing','src/app.js · stopPanelHtml','Keep going, pick another test or return home.'],
 ['results','Practice results','existing','src/app.js · renderResults','Score, elapsed time and missed-route review.'],
 ['log','Shift log','existing','src/app.js · showLog','Local attempt history, export and clear actions.'],
 ['log-empty','Empty shift log','existing','src/app.js · showLog','History before any completed practice test.'],
 ['ranked','Ranked hub','concept','mockups/entry-navigation.html · issue #17','Navigation established; content is a placeholder.'],
 ['leaderboard','Leaderboard','concept','mockups/entry-navigation.html · issue #16','Member-only path; final content is undecided.'],
 ['profile','Profile','concept','mockups/entry-navigation.html · issue #16','Member identity, Support and Log out path only.'],
 ['tickets','Support / Tickets','concept','mockups/entry-navigation.html · issue #26','Ticket path only; no ticket form has been designed.'],
].map(([id,title,status,source,description])=>({id,title,status,source,description}));

export function filterScreens(query='', status='all') {
 const term=query.trim().toLowerCase();
 return screens.filter(s=>(status==='all'||s.status===status)&&`${s.title} ${s.id} ${s.description}`.toLowerCase().includes(term));
}
