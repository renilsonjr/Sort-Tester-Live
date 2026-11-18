# Glassmorphism App Redesign Implementation Plan

> **Goal:** Repaginar a interface completa do Sort Lab (Login/Auth, Perfil, Modo Ranqueado e Quiz Gameplay) com a estética **Glassmorphism Trivia UI**, preservando a paleta de cores Saddle Brook Twilight, a tipografia `Nunito` e integrando feedback sonoro procedural via Web Audio API e animações das esteiras de triagem (belts).

---

## 1. Visão Geral da Arquitetura Visual

### 1.1 Tokens de Design & Glassmorphism
- **Cores Oficiais Mantidas:**
  - Ink: `#35271e`
  - Muted: `#7d6b5c`
  - Brand: `#38261b`
  - Accent / Gold: `#f4bd38` (com linha `#b47d15` e glow `rgba(244, 189, 56, 0.4)`)
  - Faixas de Esteira (Belts): `BELT_STYLE` em `src/belts.js` (Gold, Blue, Orange, Brown, Yellow, Green, Pink, Red, Purple, Check)
  - Feedback: `#226442` (Acerto) e `#a12d2d` (Erro)
- **Glassmorphism Refinado:**
  - Superfícies com `backdrop-filter: blur(20px - 28px)`
  - Bordas lineares translúcidas com specular highlight superior
  - Orbes de iluminação difusa (ambient glow) por trás dos cartões de vidro
  - Floating Dock de navegação arredondado com efeito de pílula

### 1.2 Feedback Gamificado & Áudio
- **Web Audio API Procedural (`src/sound.js`):**
  - Acerto: arpeggio ascendente alegre (C5, E5, G5, C6)
  - Erro: buzzer suave descendente (A3, F3)
  - Trilha sonora de fundo suave (BGM) opcional
- **Animações de Feedback:**
  - `correctGlow`: pulsação com anel de luz verde nas esteiras corretas
  - `incorrectShake`: tremor lateral com luz vermelha em respostas erradas
  - Mascote reativo: troca de estados (`thinking`, `correct`, `incorrect`) e balão de expressão

---

## 2. Fases de Execução

### Fase 1: Fundação & Design Tokens Globais
- **Arquivos:** `mockups/design-library/library.css`, `index.html`
- **Atividades:**
  - Declarar as variáveis `:root` de Glassmorphism (`--glass-surface`, `--glass-border`, `--glass-shadow`, `--dock-bg`, etc.).
  - Implementar suporte a classes utilitárias para cards translúcidos e ambient orbs.
  - Assegurar compatibilidade de contraste e suporte a `prefers-reduced-motion`.

### Fase 2: Shell Global & Floating Glass Dock
- **Arquivos:** `index.html`, `src/app.js`
- **Atividades:**
  - Substituir a barra de abas tradicional pela barra flutuante `glass-dock` no rodapé da aplicação.
  - Ajustar o container de viewport mobile (`#app`) para acomodar a navegação flutuante sem sobreposição de conteúdo (`padding-bottom: 96px`).
  - Atualizar o mini-header com pílula de perfil do usuário e pontuação em tempo real.

### Fase 3: Tela de Login & Fluxo de Entrada
- **Arquivos:** `index.html`, `src/app.js`
- **Atividades:**
  - Montar o card central de vidro com o badge-logo inclinado `◆`.
  - Estilizar os inputs com fundo translúcido, borda sutil e foco dourado luminoso.
  - Implementar os botões de ação primária com gradiente dourado e botão secundário translúcido para acesso visitante.

### Fase 4: Modo Ranqueado (Leaderboard & Pódio 3D)
- **Arquivos:** `src/app.js`, `index.html`
- **Atividades:**
  - Criar o pódio gamificado do Top 3 em perspectiva de vidro, coroando o 1º lugar.
  - Exibir a lista de classificação geral com identificadores visuais de esteira (`belt-tag`).
  - Destacar a posição e pontuação atual do próprio usuário com borda luminosa.

### Fase 5: Quiz Gameplay & Integração de Som Procedural
- **Arquivos:** `src/app.js`, `src/sound.js`, `index.html`
- **Atividades:**
  - Estruturar a barra de progresso em vidro neon e o contador circular de tempo.
  - Implementar o card de pergunta suspenso e o grid 2x2 de esteiras (`belt-option-btn`).
  - Vincular os eventos de clique às funções `playCorrectSfx()` e `playIncorrectSfx()`.
  - Integrar as classes de animação `feedback-correct` (`correctGlow`) e `feedback-incorrect` (`incorrectShake`).
  - Conectar as reações dinâmicas da imagem do mascote às respostas.

### Fase 6: Tela de Perfil do Usuário
- **Arquivos:** `src/app.js`, `index.html`
- **Atividades:**
  - Apresentar o avatar do usuário com badge de faixa (`Gold Belt`).
  - Montar o grid de 3 métricas principais (Pontos, Precisão, Ranking) em cartões de vidro.
  - Renderizar a galeria horizontal de emblemas e conquistas (`badge-gold`, `badge-challenger`, etc.).

---

## 3. Critérios de Aceitação & Verificação
1. **Fidelidade Visual:** Todas as quatro telas (Login, Perfil, Ranked e Quiz) devem refletir a referência do Dribbble sem perder a paleta de cores e tipografia da marca.
2. **Desempenho & Acessibilidade:** Taxa de quadros fluida (60fps) nas transições de tela e respeito total às preferências de redução de movimento.
3. **Áudio:** O áudio procedural não deve gerar ruídos ou atrasos, respeitando o estado mudo do usuário.
4. **Testes Automatizados:** Manutenção de 100% dos testes unitários e de integração existentes passando sem regressões.
