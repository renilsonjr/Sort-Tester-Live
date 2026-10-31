import { CHART, STATE_NAMES_ES } from './chart.js';

const KEY = 'sortTest.language.v1';

const ES = {
  'Independent practice': 'Práctica independiente',
  'Main navigation': 'Navegación principal',
  'Home': 'Inicio',
  'Study': 'Estudiar',
  'Quiz': 'Prueba',
  'Sort practice, one route at a time': 'Practica la clasificación, una ruta a la vez',
  'Practice': 'Practica',
  'the chart.': 'la tabla.',
  'Learn the belt. Then test your recall.': 'Aprende el color. Luego comprueba lo que recuerdas.',
  'Where do you want to start?': '¿Por dónde quieres empezar?',
  'Know the chart': 'Conoce la tabla',
  'Browse every service by state and ZIP range.': 'Consulta cada servicio por estado y rango de ZIP.',
  'Take a quiz': 'Haz una prueba',
  'Start with Ground, then build up to the full chart.': 'Empieza con Ground y avanza hasta toda la tabla.',
  'Shift log': 'Registro del turno',
  'This phone is not saving results. Each score is shown once and then gone.': 'Este teléfono no guarda los resultados. Cada nota se muestra una sola vez.',
  'Made by RJ.': 'Creado por RJ.',
  'Not affiliated with or endorsed by UPS. This practice does not replace any required UPS test or training. Follow your current worksite chart and instructions.': 'No está afiliado a UPS ni cuenta con su aprobación. Esta práctica no reemplaza ninguna prueba ni capacitación obligatoria de UPS. Sigue la tabla y las instrucciones vigentes en tu lugar de trabajo.',
  'Ready to practice?': '¿Listo para practicar?',
  'Who is taking the test?': '¿Quién hará la prueba?',
  'Quiz yourself': 'Ponte a prueba',
  'A name or ID is optional. If you leave it blank, your result appears as Guest in the shift log on this phone.': 'El nombre o ID es opcional. Si lo dejas en blanco, tu resultado aparecerá como Invitado en el registro de este teléfono.',
  'Name or ID (optional)': 'Nombre o ID (opcional)',
  'Guest': 'Invitado',
  'e.g. J. Rivera': 'p. ej., J. Rivera',
  'Pick a test': 'Elige una prueba',
  'Back to home': 'Volver al inicio',
  'Twilight study guide': 'Guía de estudio Twilight',
  'Know the chart.': 'Conoce la tabla.',
  'Choose a service, then read its states, ZIP ranges, belts, and exceptions.': 'Elige un servicio y consulta sus estados, rangos ZIP, colores y excepciones.',
  'Choose service': 'Elige un servicio',
  'Twilight chart': 'Tabla Twilight',
  '{shown} of {total} routes shown': '{shown} de {total} rutas visibles',
  'Find a state or number': 'Busca un estado o número',
  'New Jersey, 079-9, California, 155': 'Nueva Jersey, 079-9, California, 155',
  'Main chart': 'Tabla principal',
  'Exceptions and special rules': 'Excepciones y reglas especiales',
  'No matching routes in this service.': 'No hay rutas que coincidan en este servicio.',
  'This study guide does not replace your current worksite chart or UPS training.': 'Esta guía no reemplaza la tabla vigente de tu lugar de trabajo ni la capacitación de UPS.',
  'Time to practice': 'Hora de practicar',
  '{name} · Four belt choices per card. The clock starts when the first card appears.': '{name} · Cuatro colores por tarjeta. El reloj comienza al mostrar la primera.',
  'New challenge levels': 'Nuevos niveles',
  'Current quizzes · Twilight': 'Pruebas actuales · Twilight',
  '{count} questions · {seconds}s each': '{count} preguntas · {seconds} s cada una',
  '{count} cards · {seconds}s each': '{count} tarjetas · {seconds} s cada una',
  'Not checked against the chart yet': 'Aún no se verificó con la tabla',
  'Edit name (optional)': 'Editar nombre (opcional)',
  'Main page': 'Página principal',
  'Card {current} of {total}': 'Tarjeta {current} de {total}',
  'Question {current} of {total}': 'Pregunta {current} de {total}',
  'Time to choose': 'Tiempo para elegir',
  'Where does this go?': '¿A qué color va?',
  'Blue mascot thinking with a question mark': 'Personaje azul pensando con un signo de interrogación',
  'Happy blue mascot': 'Personaje azul feliz',
  'Sad blue mascot': 'Personaje azul triste',
  'Cancel': 'Cancelar',
  'Test stopped': 'Prueba detenida',
  'Nothing is saved until a test is finished, so leaving now records nothing.': 'No se guarda nada hasta terminar la prueba. Si sales ahora, no se registrará ningún resultado.',
  'Keep going': 'Continuar',
  'Pick another test': 'Elegir otra prueba',
  'Correct': 'Correcto',
  'Correct!': '¡Correcto!',
  'Out of time': 'Se acabó el tiempo',
  'Missort': 'Clasificación incorrecta',
  'Review this route': 'Revisa esta ruta',
  'Your choice': 'Tu respuesta',
  'Correct belt': 'Color correcto',
  'No choice': 'Sin respuesta',
  'Continue': 'Continuar',
  'Next question starts automatically': 'La siguiente pregunta empieza automáticamente',
  'Score': 'Puntuación',
  'Time': 'Tiempo',
  'This result was not saved. This phone is not saving results.': 'Este resultado no se guardó. Este teléfono no está guardando resultados.',
  'No missorts.': 'Sin errores de clasificación.',
  'Missed': 'Errores',
  'said {answer}': 'respondió {answer}',
  'ran out of time': 'se acabó el tiempo',
  'Back to main page': 'Volver a la página principal',
  'Nothing recorded yet.': 'Todavía no hay resultados.',
  'Export to Excel': 'Exportar a Excel',
  'Clear log': 'Borrar registro',
  'Tap again to erase every result': 'Toca otra vez para borrar todos los resultados',
  'Preparing the sheet...': 'Preparando la hoja...',
  'Saved.': 'Guardado.',
  'Sent.': 'Enviado.',
  'Already asking. Try again in a moment.': 'Ya se está procesando. Inténtalo de nuevo en un momento.',
  'The log is too big to send. Clear it and start a fresh shift.': 'El registro es demasiado grande. Bórralo y comienza un nuevo turno.',
  'This phone could not save the file.': 'Este teléfono no pudo guardar el archivo.',
};

const SERVICE_ES = {
  Ground: 'Terrestre',
  'Next Day Air': 'Aéreo 1 día',
  '2 Day Air': 'Aéreo 2 días',
  '3 Day Select': 'Select 3 días',
  'All Services': 'Todos los servicios',
};

const DECK_ES = {
  'level-basic': ['Básico', 'Rutas terrestres y la excepción de Nueva Jersey'],
  'level-medium': ['Intermedio', 'Rutas terrestres, aéreas de 2 días y de 3 días, más algunas aéreas de 1 día'],
  'level-hard': ['Difícil', 'Toda la tabla, diferencias entre servicios y excepciones'],
  'common-twilight-1': ['Errores comunes · Serie 1', 'Rutas que suelen confundirse, con la regla actual de Nueva Jersey'],
  'common-twilight-2': ['Errores comunes · Serie 2', 'Una segunda serie con otros ejemplos de Nueva Jersey'],
  'new-york': ['Nueva York', 'Rangos, límites y excepciones de Nueva York'],
  'next-day-air': ['Aéreo 1 día', 'El servicio con más excepciones'],
  'two-day-air': ['Aéreo 2 días', 'Rutas que cambian con respecto al servicio terrestre'],
  'three-day-select': ['Select 3 días', 'Límites y rangos intermedios'],
};

const DETAIL_ES = {
  '079 9 is ORANGE': '079 9 va a ORANGE',
  '148 1 is GOLD': '148 1 va a GOLD',
  '3 Day Select exception': 'Excepción de 3 Day Select',
  '376–378 is BLUE': '376–378 va a BLUE',
  'Exception survives sort change': 'La excepción sigue vigente tras el cambio',
  'Ground exception': 'Excepción de Ground',
  'Ground, 2 Day Air, 3 Day Select only': 'Solo terrestre, aéreo de 2 días y Select de 3 días',
  'NJ list': 'Lista de Nueva Jersey',
  'Only orange NJ code': 'Único código de NJ que va a ORANGE',
  'Single-code exception': 'Excepción de un solo código',
  'Sort change': 'Cambio de clasificación',
  'Sort change; overrides BROWN': 'Cambio de clasificación; reemplaza BROWN',
  'Termination overrides ZIP range': 'La terminación prevalece sobre el rango ZIP',
};

export function createLanguage(storage) {
  let code = 'en';
  try {
    if (storage?.getItem(KEY) === 'es') code = 'es';
  } catch { /* Language choice is usable for this visit without storage. */ }

  return {
    get code() { return code; },
    set(next) {
      if (next !== 'en' && next !== 'es') return;
      code = next;
      try { storage?.setItem(KEY, next); } catch { /* Keep the choice in memory. */ }
    },
    text(source, values = {}) {
      const template = code === 'es' ? ES[source] ?? source : source;
      return template.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? ''));
    },
    service(source) { return code === 'es' ? SERVICE_ES[source] ?? source : source; },
    deckName(deck) { return code === 'es' ? DECK_ES[deck.id]?.[0] ?? deck.name : deck.name; },
    deckBlurb(deck) { return code === 'es' ? DECK_ES[deck.id]?.[1] ?? deck.blurb : deck.blurb; },
    deckLabel(label) {
      if (code !== 'es') return label;
      const names = {
        'Common Missorts · Set 1 · Twilight': 'Errores comunes · Serie 1 · Twilight',
        'Common Missorts · Set 2 · Twilight': 'Errores comunes · Serie 2 · Twilight',
        'Basic · Twilight': 'Básico · Twilight',
        'Medium · Twilight': 'Intermedio · Twilight',
        'Hard · Twilight': 'Difícil · Twilight',
        'New York · Twilight': 'Nueva York · Twilight',
      };
      return names[label] ?? label;
    },
    detail(source) { return code === 'es' ? DETAIL_ES[source] ?? source : source; },
    state(source) {
      if (code !== 'es') return source === '*' ? 'All states (*)' : source;
      if (source === '*' || source === 'All states') return 'Todos los estados (*)';
      if (source === 'Any state') return 'Cualquier estado';
      return source.split(',').map(part => STATE_NAMES_ES[part.trim()] ?? part.trim()).join(', ');
    },
    explanation(response) {
      if (code !== 'es') return response.why;
      if (response.code.endsWith('2S')) return 'La terminación 2S va a BLUE en todos los servicios, sin importar el rango ZIP.';
      if (response.code.endsWith('1S')) return 'La terminación 1S va a PURPLE en todos los servicios, sin importar el rango ZIP.';
      if (response.state === 'NJ') return response.code === '079 9'
        ? '079 9 es la excepción de Nueva Jersey: ORANGE en lugar de RED.'
        : 'Nueva Jersey va a RED. Solo 079 9 va a ORANGE.';
      const service = { GND: 'Ground', GRD: 'Ground', NDA: 'Next Day Air', '2DA': '2 Day Air', '3DS': '3 Day Select', ALL: 'All Services' }[response.svc];
      const normalize = value => String(value).replace(/[^A-Z0-9]/gi, '').toUpperCase();
      const section = CHART[service];
      const row = section && [...section.main, ...section.exceptions].find(([state, route]) =>
        normalize(state === '*' ? 'All states' : state) === normalize(response.state) && normalize(route) === normalize(response.code));
      const detail = row?.[3] ? `${DETAIL_ES[row[3]] ?? row[3]}. ` : '';
      return `${detail}En Twilight, ${this.service(service ?? response.svc)} · ${response.state} · ${response.code} va a ${response.correctBelt}.`;
    },
  };
}
