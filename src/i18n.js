import { CHART, STATE_NAMES_ES } from './chart.js?v=chart-destination-20261108-r2';

const KEY = 'sortTest.language.v1';

const ES = {
  'Independent practice': 'Práctica independiente',
  // The promotion celebration (#95)
  'Skip animation': 'Saltar la animación',
  'That was the last one.': 'Esa fue la última.',
  'Promoted to': 'Ascendido a',
  'Fifteen out of fifteen. The new badge is yours.': 'Quince de quince. La nueva insignia es tuya.',
  'You are': 'Eres',
  'Promotion': 'Ascenso',
  'passed': 'superado',
  // The home poster's own words, for the people who hear the page instead
  // of seeing it. The image itself is not translated.
  'Sort Tester Live. Play for points. Reach the top 3. Win a UPS hat. Practice. Compete. Climb the leaderboard. A brown UPS cap above a gold winners’ podium.':
    'Sort Tester Live. Juega por puntos. Llega al top 3. Gana una gorra de UPS. Practica. Compite. Sube en la clasificación. Una gorra marrón de UPS sobre un podio dorado de ganadores.',
  'Main navigation': 'Navegación principal',
  'Home': 'Inicio',
  'Study': 'Estudiar',
  'Quiz': 'Prueba',
  'Sort practice, one route at a time': 'Practica la clasificación, una ruta a la vez',
  'Practice': 'Practica',
  'Ranked': 'Clasificatorio',
  'Pre-Season': 'Pretemporada',
  'The official season has started': 'La temporada oficial ha empezado',
  'These standings win no prize. Everyone goes back to 0 points and Iron when the official season starts.': 'Esta clasificación no da premio. Todos vuelven a 0 puntos e Iron cuando empiece la temporada oficial.',
  'Nobody has completed a Ranked quiz in Pre-Season yet, so there is nothing to rank.': 'Nadie ha completado una prueba del Clasificatorio en la Pretemporada, así que todavía no hay nada que clasificar.',
  'You are not in the standings yet': 'Todavía no estás en la clasificación',
  'Complete one Ranked quiz and you will appear here. Pre-Season needs no approval.': 'Completa una prueba del Clasificatorio y aparecerás aquí. La Pretemporada no requiere aprobación.',
  'It started on': 'Empezó el',
  'and ends on': 'y termina el',
  'Everyone began again at 0 points and Iron.': 'Todos volvieron a empezar con 0 puntos e Iron.',
  'Log in to play for points this season.': 'Inicia sesión para jugar por puntos esta temporada.',
  'Pre-Season. No start date has been announced for the official season.': 'Pretemporada. No se ha anunciado fecha de inicio para la temporada oficial.',
  'Pre-Season is finishing.': 'La Pretemporada está terminando.',
  'Pre-Season is closed.': 'La Pretemporada está cerrada.',
  'Pre-Season is over.': 'La Pretemporada terminó.',
  'The official season is open.': 'La temporada oficial está abierta.',
  'The season is closing. Attempts already started have five more minutes.': 'La temporada se está cerrando. Los intentos ya empezados tienen cinco minutos más.',
  'The season is closed. Standings are provisional while settlement and any tie-breaks finish.': 'La temporada está cerrada. La clasificación es provisional mientras terminan la liquidación y los desempates.',
  'Final results for this season.': 'Resultados finales de esta temporada.',
  'Closes': 'Cierra',
  'Start Ranked quiz': 'Empezar prueba del Clasificatorio',
  'Start promotion': 'Empezar el ascenso',
  '15 questions, ten seconds each.': '15 preguntas, diez segundos cada una.',
  'You are at the cap, so promotion is the only Ranked quiz available. It needs a perfect 15 out of 15. Practice is available as usual and never changes these points.': 'Estás en el tope, así que el ascenso es la única prueba del Clasificatorio disponible. Necesita un 15 de 15 perfecto. La práctica sigue disponible y nunca cambia estos puntos.',
  'Playing a Ranked quiz is being built. Nothing has started.': 'Jugar una prueba del Clasificatorio está en construcción. No ha empezado nada.',
  'Could not load the season. Your points are safe.': 'No se pudo cargar la temporada. Tus puntos están a salvo.',
  'Profile': 'Perfil',
  'Profile sections': 'Secciones del perfil',
  'Overview': 'Resumen',
  'Settings': 'Ajustes',
  'Loading…': 'Cargando…',
  'Tag': 'Etiqueta',
  'Your balance': 'Tu saldo',
  'points': 'puntos',
  'points to the cap': 'puntos para el tope',
  'at the cap': 'en el tope',
  'no cap': 'sin tope',
  'a negative total stays in Iron': 'un total negativo se queda en Iron',
  'Promotion available': 'Ascenso disponible',
  'A perfect 15 out of 15 quiz moves you up. Start promotion is on the Ranked screen; nothing starts from here.': 'Una prueba perfecta de 15 de 15 te sube. Empezar el ascenso está en la pantalla de Clasificatorio; aquí no empieza nada.',
  'How badges work': 'Cómo funcionan las insignias',
  'you are here': 'estás aquí',
  'One balance decides your badge. Reaching a cap makes promotion available; only a perfect promotion quiz moves you up.': 'Un solo saldo decide tu insignia. Llegar al tope habilita el ascenso; solo una prueba de ascenso perfecta te sube.',
  'Only you can see this. Pre-Season results never count toward the official season.': 'Solo tú ves esto. Los resultados de la Pretemporada nunca cuentan para la temporada oficial.',
  'You played no Ranked quizzes during Pre-Season, so there is nothing here.': 'No jugaste ninguna prueba del Clasificatorio en la Pretemporada, así que aquí no hay nada.',
  'Ranked quiz': 'Prueba del Clasificatorio',
  'Completed': 'Completada',
  'Ended at launch · no score applied': 'Terminada al lanzamiento · sin puntuación aplicada',
  'Could not load your balance. Your points are safe.': 'No se pudo cargar tu saldo. Tus puntos están a salvo.',
  'Could not load your history. Your attempts are safe.': 'No se pudo cargar tu historial. Tus intentos están a salvo.',
  'Support': 'Soporte',
  'Tickets': 'Casos',
  'Create ticket': 'Crear caso',
  'About one of your own Ranked attempts.': 'Sobre uno de tus propios intentos del Clasificatorio.',
  'Only you can see your tickets. When a ticket is closed, its description and connection details are deleted 15 days later. Evidence shared with another case that is still open is kept until that case closes.': 'Solo tú ves tus casos. Cuando un caso se cierra, su descripción y sus detalles de conexión se eliminan 15 días después. La evidencia compartida con otro caso que sigue abierto se conserva hasta que ese caso se cierre.',
  'You have no tickets. Support only opens one when you ask for it: nothing here is created automatically, and a connection problem does not open a ticket by itself.': 'No tienes casos. Soporte solo abre uno cuando tú lo pides: aquí nada se crea solo, y un problema de conexión no abre un caso por sí mismo.',
  'Opening a ticket never changes your points or your access.': 'Abrir un caso nunca cambia tus puntos ni tu acceso.',
  'Which attempt': 'Qué intento',
  'What happened (optional)': 'Qué pasó (opcional)',
  'Anything that helps. You can leave this empty.': 'Lo que ayude. Puedes dejarlo vacío.',
  'Sent with your ticket': 'Se envía con tu caso',
  'The attempt you picked and the connection events recorded for it. Only you and the people reviewing your ticket can see them. Your tickets never appear on your profile or the leaderboard.': 'El intento que elegiste y los eventos de conexión registrados para él. Solo tú y quienes revisan tu caso pueden verlos. Tus casos nunca aparecen en tu perfil ni en la clasificación.',
  'Send ticket': 'Enviar caso',
  'Ticket sent': 'Caso enviado',
  'Someone will look at it. You can close the app; nothing is waiting on you.': 'Alguien lo va a revisar. Puedes cerrar la aplicación; nada depende de ti.',
  'This does not change your points or your access, whatever the outcome is.': 'Esto no cambia tus puntos ni tu acceso, sea cual sea el resultado.',
  'Back to your tickets': 'Volver a tus casos',
  'A ticket is about a Ranked attempt, and you have none yet.': 'Un caso trata sobre un intento del Clasificatorio, y todavía no tienes ninguno.',
  'A ticket about this attempt is already open.': 'Ya hay un caso abierto sobre este intento.',
  'Could not send the ticket. Nothing was sent.': 'No se pudo enviar el caso. No se envió nada.',
  'Could not load your tickets. Your tickets and your points are safe.': 'No se pudieron cargar tus casos. Tus casos y tus puntos están a salvo.',
  'Your tickets.': 'Tus casos.',
  'Delete account': 'Eliminar la cuenta',
  'Are you sure you want to proceed with deleting this account?': '¿Seguro que quieres continuar y eliminar esta cuenta?',
  'I agree to delete my account. I understand that deleting it before prizes are finalized removes this account from this season\u2019s competition.': 'Acepto eliminar mi cuenta. Entiendo que eliminarla antes de que se definan los premios saca a esta cuenta de la competencia de esta temporada.',
  'After deletion is completed, your profile, quiz history and points are removed. A new account starts at 0 points / Iron.': 'Cuando la eliminación termine, se quitan tu perfil, tu historial de pruebas y tus puntos. Una cuenta nueva empieza con 0 puntos / Iron.',
  'Your profile, quiz history and points are deleted. We keep only a private season-ineligibility record until prizes are finalized.': 'Se eliminan tu perfil, tu historial de pruebas y tus puntos. Solo conservamos un registro privado de inelegibilidad de temporada hasta que se definan los premios.',
  'Tick the box above to continue.': 'Marca la casilla de arriba para continuar.',
  'This cannot be undone': 'Esto no se puede deshacer',
  'Once this is accepted there is no undo and no restore.': 'Una vez aceptado no hay forma de deshacerlo ni de restaurarlo.',
  'Login ID': 'ID de acceso',
  'Cancel': 'Cancelar',
  'That did not work. Nothing has been deleted.': 'No funcionó. No se ha eliminado nada.',
  'The owner account cannot be deleted.': 'La cuenta del dueño no se puede eliminar.',
  'Too many attempts. Wait a moment and try again.': 'Demasiados intentos. Espera un momento e inténtalo de nuevo.',
  'Could not reach the server. Nothing has been deleted.': 'No se pudo contactar al servidor. No se ha eliminado nada.',
  'Account': 'Cuenta',
  'Deletion accepted': 'Eliminación aceptada',
  'You have been signed out and this account can no longer be used. Removing your data is under way.': 'Se cerró tu sesión y esta cuenta ya no se puede usar. La eliminación de tus datos está en curso.',
  'There is no undo and nothing to restore. A new account would start at 0 points and Iron, and cannot get this season\u2019s prizes back.': 'No hay forma de deshacerlo ni nada que restaurar. Una cuenta nueva empezaría con 0 puntos e Iron, y no puede recuperar los premios de esta temporada.',
  'Support is being built.': 'El soporte está en construcción.',
  'Removes your profile, history and points.': 'Elimina tu perfil, tu historial y tus puntos.',
  'Support and account deletion are being built.': 'El soporte y la eliminación de la cuenta están en construcción.',
  'Study and practice': 'Estudia y practica',
  'Practice never changes Ranked points.': 'La práctica nunca cambia los puntos del Clasificatorio.',
  'Ranked is being built': 'El Clasificatorio está en construcción',
  'Playing for points is not available yet. Practice is, and it never changes Ranked points.': 'Jugar por puntos aún no está disponible. La práctica sí, y nunca cambia los puntos del Clasificatorio.',
  'Your profile is being built': 'Tu perfil está en construcción',
  'Your points, badge and history will appear here.': 'Aquí aparecerán tus puntos, tu insignia y tu historial.',
  'the chart.': 'la tabla.',
  'Learn the belt. Then test your recall.': 'Aprende el color. Luego comprueba lo que recuerdas.',
  'Recent sort changes': 'Cambios recientes de clasificación',
  'For NY 140–147, 2 Day Air and 3 Day Select stay ORANGE; Next Day Air stays PURPLE. NY 148–149 stays ORANGE on Ground, 2 Day Air and 3 Day Select, except 148 1 goes GOLD.': 'Para NY 140–147, Aéreo 2 días y Select 3 días siguen en ORANGE; Aéreo 1 día sigue en PURPLE. NY 148–149 sigue en ORANGE en Terrestre, Aéreo 2 días y Select 3 días, excepto 148 1, que va a GOLD.',
  'Where do you want to start?': '¿Por dónde quieres empezar?',
  'Playing as guest': 'Jugando como invitado',
  'Sign in to compete in Ranked': 'Inicia sesión para competir en el Clasificatorio',
  'Sign in': 'Iniciar sesión',
  'Play Ranked': 'Jugar Clasificatorio',
  'Switch between day and night': 'Cambiar entre día y noche',
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
  // The owner's recovery-message inbox (#251)
  'Recovery messages': 'Mensajes de recuperación',
  'Left on the sign-in screen by people who are locked out.': 'Dejados en la pantalla de acceso por personas que no pueden entrar.',
  'A message proves nothing about who wrote it. Find the person, check them in person, then use Access recovery.': 'Un mensaje no prueba quién lo escribió. Busca a la persona, compruébala en persona y luego usa Recuperación de acceso.',
  'Open Access recovery': 'Abrir Recuperación de acceso',
  'Mark as resolved': 'Marcar como resuelto',
  'No messages.': 'No hay mensajes.',
  'resolved': 'resuelto',
  'received': 'recibido',
  'Could not load the messages. Nothing has been changed.': 'No se pudieron cargar los mensajes. No se ha cambiado nada.',
  '1 message waiting.': '1 mensaje en espera.',
  'messages waiting.': 'mensajes en espera.',
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
  'mixed-missorts': ['Errores comunes · Mixto', 'Aéreo 2 días en IN/OH/MI/IL, NY 128-147, MA 025-026, CA 900-935/936-961 y NH'],
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
  'Listed NJ preload exception': 'Excepción indicada en la lista de precarga de NJ',
  'Use listed NJ preload codes': 'Consulta los códigos indicados en la lista de precarga de NJ',
  'Ground-only owner correction': 'Corrección confirmada solo para el servicio terrestre',
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
        'Common Missorts · Mixed · Twilight': 'Errores comunes · Mixto · Twilight',
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
      if (response.destinationModifier === '+1') return code === 'es'
        ? 'El indicador de destino +1 va a PURPLE en los cuatro servicios. El código de ruta no cambia.'
        : 'The destination indicator +1 goes to PURPLE on all four services. The routing code stays unchanged.';
      if (code !== 'es') return response.why;
      if (response.code.endsWith('2S')) return 'La terminación 2S va a BLUE en todos los servicios, sin importar el rango ZIP.';
      if (response.code.endsWith('1S')) return 'La terminación 1S va a PURPLE en todos los servicios, sin importar el rango ZIP.';
      if (response.state === 'NJ') return response.code === '079 9'
        ? 'El código de precarga de Nueva Jersey 079 9 va a ORANGE en todos los servicios.'
        : `El código de precarga de Nueva Jersey ${response.code} va a ${response.correctBelt}. Consulta la lista de precarga; el rango general de NJ indica CHECK.`;
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
