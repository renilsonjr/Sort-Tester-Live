// Twilight chart transcribed for the approved study and quiz design.
// Keep worksite corrections here so study and generated quiz cards share one answer key.
    const rows = text => text.trim().split('\n').map(line => line.split('|').map(value => value.trim()));
    // The four main columns in the supplied Twilight chart, with the already
    // established sort changes and the user's NJ rule applied for this mock.
    const sharedEast = rows(`
      MA|010–024|GOLD
      MA|025–026|BLUE
      MA, RI|027–029|GOLD
      NH|030–033|BLUE
      NH|034 0|GOLD
      NH, ME|035–049|BLUE
      VT|050–059|GOLD
      CT|060–069|GOLD
      NJ|070–089|RED|079 9 is ORANGE
      NY|100–108|YELLOW
      NY|109|ORANGE
      NY|110–119|PINK
      NY|120–121|GOLD|Sort change
      NY|122–127|ORANGE
      NY|128–139|GOLD
      NY|140–147|ORANGE
      NY|148–149|ORANGE|148 1 is GOLD
      PA|150–167|GREEN
      PA|168–178|GREEN
      PA|179–189|GREEN
      PA|190–194|ORANGE
      PA, DE|195–199|GREEN
      DC, MD|200–219|GREEN
      VA|220–238|YELLOW
      VA, WV|239–269|YELLOW
      NC, SC|270–299|YELLOW
    `);
    const groundMain = [...sharedEast, ...rows(`
      GA|300–319|BLUE
      FL|320–349|PINK
      AL|350–369|BLUE
      TN|370–385|BROWN|376–378 is BLUE
      MS|386–399|BROWN
      KY|400–429|BROWN
      OH|430–459|ORANGE
      IN|460–479|ORANGE
      MI|480–497|ORANGE
      *|498–589|BROWN
      MT|590–599|ORANGE
      IL|600–608|YELLOW
      IL|609–619|ORANGE
      IL|620–629|ORANGE
      MO, KS|630–674|BLUE
      KS|675–679|ORANGE
      NE|680–689|BLUE
      NE|690–699|ORANGE
      LA, AR|700–729|BLUE
      OK|730–734|ORANGE
      OK|735–749|ORANGE
      TX|750–779|BLUE
      TX|780–784|BLUE
      TX|785–799|ORANGE
      CO, WY|800–831|ORANGE
      ID|832–839|BROWN
      UT|840–849|ORANGE
      AZ, NM|850–884|BLUE
      NV|889–891|BLUE
      NV|893–899|ORANGE
      CA|900–935|RED
      CA|936–961|BROWN
      HI|967–968|ORANGE
      OR, WA|970–994|BROWN
      AK|995–999|BROWN
      MEX|MEXICO|GREEN
      CAN|CANADA|PURPLE
      PRI|PR|PINK
    `)];
    const threeDayMain = [...sharedEast, ...rows(`
      GA|300–319|BLUE
      FL|320–349|PINK
      AL|350–369|BLUE
      TN|370–385|BROWN
      MS|386–399|BROWN
      KY|400–429|BROWN
      OH|430–459|ORANGE
      IN|460–479|ORANGE
      MI|480–497|ORANGE
      *|498–566|BROWN
      *|567–599|BLUE
      IL|600–608|YELLOW
      IL|609–629|ORANGE
      MO, KS|630–674|BLUE
      KS|675–679|ORANGE
      NE|680–689|BLUE
      NE|690–699|ORANGE
      *|700–734|BLUE
      OK|735–749|ORANGE
      TX|750–768|PURPLE
      TX|769 0|PURPLE
      TX|770–784|PURPLE
      TX|785–799|PURPLE
      CO|800–810|ORANGE
      *|811–999|PURPLE
    `)];
    const twoDayMain = [...sharedEast, ...rows(`
      GA|300–319|PURPLE
      FL|320–349|PURPLE
      AL|350–369|PURPLE
      TN|370–385|PURPLE
      MS|386–399|PURPLE
      KY|400–419|BROWN
      KY|420|PURPLE
      KY|421–429|BROWN
      OH|430–459|ORANGE
      IN|460–479|PURPLE
      MI|480–497|ORANGE
      *|498–599|PURPLE
      IL|600–619|PURPLE
      IL|620–629|ORANGE
      MO|630–639|BLUE
      *|640–729|PURPLE
      OK|730–740|PURPLE
      OK|741 9|ORANGE|Single-code exception
      OK|742–749|PURPLE
      *|750–999|PURPLE
      *|WORLD|PURPLE
    `)];
    const nextDayMain = rows(`
      MA|010–024|GOLD
      MA|025–026|PURPLE
      MA, RI|027–029|GOLD
      NH|030–033|PURPLE
      NH|034 0|GOLD
      NH, ME|035–049|PURPLE
      VT|050–059|GOLD
      CT|060–069|GOLD
      NJ|070–089|RED|079 9 is ORANGE
      NY|100–108|YELLOW
      NY|109|ORANGE
      NY|110–119|PINK
      NY|120–121|GOLD|Sort change
      NY|122–127|ORANGE
      NY|128–135|GOLD
      NY|136|PURPLE|Exception survives sort change
      NY|137–139|GOLD
      NY|140–149|PURPLE
      PA|150–167|PURPLE
      PA|168–178|GREEN
      PA|179–189|GREEN
      PA|190–194|ORANGE
      PA, DE|195–199|GREEN
      DC, MD|200–219|GREEN
      *|220–999|PURPLE
      *|WORLD|PURPLE
      *|ALL 1DA EAM|PURPLE
    `);
    const njDetails = rows(`
      NJ|070 3|RED|NJ list
      NJ|070 9|RED|NJ list
      NJ|075 9|RED|NJ list
      NJ|076 9|RED|NJ list
      NJ|077 0|RED|NJ list
      NJ|078 4|RED|NJ list
      NJ|078 9|RED|NJ list
      NJ|079 9|ORANGE|Only orange NJ code
      NJ|081 9|RED|NJ list
      NJ|082 9|RED|NJ list
      NJ|083 9|RED|NJ list
      NJ|086 0|RED|NJ list
      NJ|087 1|RED|NJ list
      NJ|088 9|RED|NJ list
      NJ|089 9|RED|NJ list
    `);
    const commonExceptions = rows(`
      NY|148 1|GOLD|Ground, 2 Day Air, 3 Day Select only
      Any state|ends 2S|BLUE|Termination overrides ZIP range
      Any state|ends 1S|PURPLE|Termination overrides ZIP range
    `);
    export const CHART = {
      Ground: {
        main: groundMain,
        exceptions: [...njDetails, ...rows(`
          TN|376–378|BLUE|Sort change; overrides BROWN
          NE|575 3-6|ORANGE|Ground exception
          NV|833 9-7|ORANGE|Ground exception
          AZ|847 2-7|BLUE|Ground exception
          NV|864 4-7|ORANGE|Ground exception
          NV|890 0-0|ORANGE|Ground exception
          AZ|922 2-0|BLUE|Ground exception
        `), ...commonExceptions],
      },
      'Next Day Air': {
        main: nextDayMain,
        exceptions: [...njDetails, ...commonExceptions.slice(1)],
      },
      '2 Day Air': {
        main: twoDayMain,
        exceptions: [...njDetails, ...commonExceptions],
      },
      '3 Day Select': {
        main: threeDayMain,
        exceptions: [...njDetails, ...rows(`
          MS|395 0|BLUE|3 Day Select exception
          SD|511 9|BLUE|3 Day Select exception
          SD|571 9|BROWN|3 Day Select exception
          ND|581 9|BROWN|3 Day Select exception
          ND|582 0|BROWN|3 Day Select exception
          TX|786 4|ORANGE|3 Day Select exception
          TX|787 9|ORANGE|3 Day Select exception
          TX|796 0|ORANGE|3 Day Select exception
          TX|799 9|ORANGE|3 Day Select exception
          CO|811 3|ORANGE|3 Day Select exception
          CO|812 0|ORANGE|3 Day Select exception
          CO|813 7|ORANGE|3 Day Select exception
          CO|816 0|ORANGE|3 Day Select exception
          CO|816 1|ORANGE|3 Day Select exception
          WY|820 0|ORANGE|3 Day Select exception
          WY|820 1|ORANGE|3 Day Select exception
        `), ...commonExceptions],
      },
    };
    export const STATE_NAMES = {
      AL:'Alabama', AK:'Alaska', AZ:'Arizona', AR:'Arkansas', CA:'California', CO:'Colorado',
      CT:'Connecticut', DE:'Delaware', DC:'District of Columbia', FL:'Florida', GA:'Georgia',
      HI:'Hawaii', ID:'Idaho', IL:'Illinois', IN:'Indiana', KS:'Kansas', KY:'Kentucky',
      LA:'Louisiana', MA:'Massachusetts', MD:'Maryland', ME:'Maine', MI:'Michigan',
      MN:'Minnesota', MO:'Missouri', MS:'Mississippi', MT:'Montana', NC:'North Carolina',
      ND:'North Dakota', NE:'Nebraska', NH:'New Hampshire', NJ:'New Jersey', NM:'New Mexico',
      NV:'Nevada', NY:'New York', OH:'Ohio', OK:'Oklahoma', OR:'Oregon', PA:'Pennsylvania',
      RI:'Rhode Island', SC:'South Carolina', SD:'South Dakota', TN:'Tennessee', TX:'Texas',
      UT:'Utah', VA:'Virginia', VT:'Vermont', WA:'Washington', WV:'West Virginia',
      WY:'Wyoming', MEX:'Mexico', CAN:'Canada', PRI:'Puerto Rico',
    };
    export const STATE_NAMES_ES = {
      AL:'Alabama', AK:'Alaska', AZ:'Arizona', AR:'Arkansas', CA:'California', CO:'Colorado',
      CT:'Connecticut', DE:'Delaware', DC:'Distrito de Columbia', FL:'Florida', GA:'Georgia',
      HI:'Hawái', ID:'Idaho', IL:'Illinois', IN:'Indiana', KS:'Kansas', KY:'Kentucky',
      LA:'Luisiana', MA:'Massachusetts', MD:'Maryland', ME:'Maine', MI:'Míchigan',
      MN:'Minnesota', MO:'Misuri', MS:'Misisipi', MT:'Montana', NC:'Carolina del Norte',
      ND:'Dakota del Norte', NE:'Nebraska', NH:'Nuevo Hampshire', NJ:'Nueva Jersey', NM:'Nuevo México',
      NV:'Nevada', NY:'Nueva York', OH:'Ohio', OK:'Oklahoma', OR:'Oregón', PA:'Pensilvania',
      RI:'Rhode Island', SC:'Carolina del Sur', SD:'Dakota del Sur', TN:'Tennessee', TX:'Texas',
      UT:'Utah', VA:'Virginia', VT:'Vermont', WA:'Washington', WV:'Virginia Occidental',
      WY:'Wyoming', MEX:'México', CAN:'Canadá', PRI:'Puerto Rico',
    };

export function searchChart(service, input = '') {
  const section = CHART[service];
  if (!section) return { main: [], exceptions: [], total: 0 };
  const normalize = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  const query = normalize(input);
  const exactState = STATE_NAMES[query] ? query : null;
  const numericSearch = String(input).trim().match(/^(?:(.+?)\s+)?(\d{3})(?:\d{2})?$/);
  const zipPrefix = numericSearch ? Number(numericSearch[2]) : null;
  const requestedState = numericSearch?.[1] ? normalize(numericSearch[1]) : null;
  const matches = row => {
    if (!query) return true;
    if (exactState) return row[0].split(',').map(code => code.trim()).includes(exactState);
    const range = row[1].match(/^(\d{3})[–-](\d{3})$/);
    const stateMatches = !requestedState || row[0].split(',').some(code => {
      const state = code.trim();
      return normalize(state) === requestedState || [STATE_NAMES[state], STATE_NAMES_ES[state]].some(name => normalize(name || '').includes(requestedState));
    });
    if (range && zipPrefix !== null && stateMatches && zipPrefix >= Number(range[1]) && zipPrefix <= Number(range[2])) return true;
    const fullStates = row[0].split(',').map(code => [STATE_NAMES[code.trim()], STATE_NAMES_ES[code.trim()]].join(' ')).join(' ');
    return normalize(row.join(' ')).includes(query) || normalize(`${fullStates} ${row[1]} ${row[2]}`).includes(query);
  };
  return {
    main: section.main.filter(matches),
    exceptions: section.exceptions.filter(matches),
    total: section.main.length + section.exceptions.length,
  };
}
