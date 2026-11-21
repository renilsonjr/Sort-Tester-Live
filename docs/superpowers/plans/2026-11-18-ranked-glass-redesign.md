# Ranked Glass Redesign (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trazer o visual glass twilight aprovado (mock `mockups/app-redesign-mock.html`) para o fluxo **Ranked** do app de produção, substituindo o creme e o glass parcial atuais, e deployar na Azure staging.

**Architecture:** Mudança só de frontend no monolito (FastAPI serve `index.html` + `src/*.js`). O CSS vive inline no `<style>` de `index.html`; as telas são renderizadas por funções em `src/app.js`. Fase 1 cobre dock + fluxo Ranked (home, quiz, feedback, resultado, leaderboard) com avatar em **stills transparentes**. Home, Prática, Perfil e Login ficam para a Fase 2 (plano separado).

**Tech Stack:** Vanilla JS (ES modules), CSS3 (backdrop-filter), Node test runner (`node --test`), Azure Container Apps (deploy manual via Cloud Shell).

## Global Constraints

- **Idioma:** UI só EN (fonte) + ES (mapas `*_ES` em `src/i18n.js`). **Nunca** português em texto de UI. Toda string nova passa por `t(...)` e ganha entrada no mapa ES.
- **Marca e regras preservadas:** marca UPS (marrom/dourado), significado das cores das belts (`src/belts.js`, `BELT_STYLE`), e as regras do Ranked (15 perguntas, 10s, pontos/cap/promoção/quit, penalidade de 10). Redesign é **só visual** — nenhuma mudança em pontuação, timer de servidor, persistência ou endpoints.
- **Acessibilidade:** foco visível, `prefers-reduced-motion` respeitado, contraste adequado sobre o vidro.
- **Dados fictícios apenas.** Avatar em produção = **stills PNG transparentes** (não o embed 3D).
- **Deploy:** só `main` e `codex/ranked-mode` publicam; Renilson roda `az` no Cloud Shell e aprova o ambiente `publish`. Runbook: `infra/azure/container-apps-app.md`.
- **Testes de DB locais** exigem a env var de Postgres (ver [[sort-tester-local-postgres-tests]]) — mas Fase 1 é frontend, então os testes relevantes são `tests/*.test.mjs` (JS, sem DB).

Referência visual: `mockups/app-redesign-mock.html`. Spec: `docs/superpowers/specs/2026-11-18-app-redesign-ux-design.md`.

---

### Task 1: Avatar stills transparentes de produção

Pré-requisito dos quizzes. O jeito limpo é re-renderizar do Blender com fundo transparente; o binário `blender` da máquina está quebrado (aponta pra `/Applications/Blender.app` inexistente).

**Files:**
- Create: `assets/avatar-thinking.png`, `assets/avatar-correct.png`, `assets/avatar-incorrect.png`, `assets/avatar-idle.png` (transparentes)
- Reference: `mockups/design-library/blender-avatar/render_app_poses.py` (poses: idle=1, thinking=114, correct=222, incorrect=282)

- [ ] **Step 1: Confirmar o Blender com Renilson.** Se ele reinstalar o Blender (ou corrigir o symlink `/opt/homebrew/bin/blender`), re-renderizar com `film_transparent = True` e `color_mode = 'RGBA'` (variante de `render_app_poses.py`). Caso contrário, usar os recortes interinos de `mockups/redesign-assets/avatar/*.png` como fallback aceito.
- [ ] **Step 2: Gerar os 4 PNGs transparentes** para `assets/` (mesma convenção dos JPGs atuais, só que `.png`).
- [ ] **Step 3: Verificar transparência** — cantos com alpha 0 (`python3 -c "from PIL import Image; ..."`).
- [ ] **Step 4: Commit** — `git add assets/avatar-*.png && git commit -m "assets: transparent avatar stills for the glass quiz"`

---

### Task 2: Fundações glass (tokens, fundo twilight, orbes)

**Files:**
- Modify: `index.html` (bloco `<style>`, variáveis `:root` e `body`/fundo)

**Interfaces:**
- Produces: tokens `--glass-surface`, `--glass-border`, `--blur-*`, `--gold`, e um fundo twilight com orbes que as tasks seguintes consomem. Mantém `BELT_STYLE` (belts) intactos.

- [ ] **Step 1:** Em `index.html`, consolidar os tokens de vidro já existentes (há ~31 trechos glass dos PRs #209–212) com os do mock (`mockups/app-redesign-mock.html` `:root`): `--glass-surface`, `--glass-surface-sub`, `--glass-border`, `--glass-highlight`, `--blur-lg/md`, `--gold`, `--gold-dark`. Definir uma única fonte de verdade no `:root`.
- [ ] **Step 2:** Trocar o fundo do app para o degradê twilight + orbes (copiar `.bg`/`.orb` do mock, adaptado): `body` ganha o degradê escuro; adicionar um elemento de orbes ambiente (fixo, `z-index:0`, `pointer-events:none`) no shell de `labPage()`.
- [ ] **Step 3:** Ajustar `--ink`/`--muted` para texto claro sobre o fundo escuro (o mock usa `--ink:#fffdf8`).
- [ ] **Step 4: Verificar no browser** — `preview_start`, abrir o app, confirmar fundo twilight sem quebrar o layout; sem overflow horizontal a 320px.
- [ ] **Step 5: Commit** — `git commit -m "style(ranked): twilight glass foundations (tokens, background, ambient orbs)"`

---

### Task 3: Remover os overrides que achatam o vidro

Hoje há regras que revertem o glass para "panel" plano (ex.: `index.html` ~linha 531 `.lab-choice { box-shadow:none; border-radius:0 }` e ~536 `.lab-nav { background: var(--panel); backdrop-filter: none }`). É a "versão que está" a eliminar.

**Files:**
- Modify: `index.html` (`<style>`, regras de override planas em `.lab-choice`, `.lab-nav`, `.lab-choice-icon`)

- [ ] **Step 1:** Localizar as regras que achatam (`backdrop-filter: none`, `border-radius: 0`, `background: var(--panel)` aplicados a `.lab-nav`/`.lab-choice`/`.lab-choice-icon`) — buscar `grep -n "backdrop-filter: none\|var(--panel)" index.html`.
- [ ] **Step 2:** Remover/neutralizar essas regras (ou a media-query/contexto que as dispara) para que o vidro das Tasks 2/4+ não seja sobrescrito. Preservar qualquer `@media (prefers-reduced-transparency)` legítimo como fallback acessível.
- [ ] **Step 3: Verificar no browser** — dock e choices renderizam como vidro, não plano.
- [ ] **Step 4: Commit** — `git commit -m "style(ranked): drop the flat overrides that reverted the glass"`

---

### Task 4: Dock flutuante de vidro

**Files:**
- Modify: `index.html` (`.lab-nav`, `.lab-nav button`, estado ativo)
- Modify: `src/app.js` (`labPage()` — só se precisar de marcação extra; a nav já existe)
- Test: `tests/nav.test.mjs` (se existir) ou asserção leve de markup

- [ ] **Step 1:** Reestilizar `.lab-nav` como dock flutuante: `position:fixed`, centralizado, `border-radius: pill`, `background: rgba(28,19,13,.82)`, `backdrop-filter: blur(20px)`, borda translúcida, sombra (copiar `.dock` do mock).
- [ ] **Step 2:** Estado ativo (`button[aria-current="page"]`) = pílula dourada com glow (gradiente `--gold`), texto escuro. Ícones/labels claros nos inativos.
- [ ] **Step 3: Verificar no browser** — dock flutua com item ativo dourado; convidado vê 2 itens, logado vê 4 (`navTabs()` já faz isso).
- [ ] **Step 4: Commit** — `git commit -m "feat(ranked): floating glass dock with gold active state"`

---

### Task 5: Ranked — telas de lista (home + leaderboard) em vidro + pódio 3D

**Files:**
- Modify: `index.html` (`.lab-screen`, `.lab-choice`, `.profile-balance`, `.board`, `.board-*`, adicionar `.podium`/`.slot`/`.pill`)
- Modify: `src/app.js` (`fillRanked`, `fillLeaderboard` — markup do pódio top-3)
- Test: `tests/ranked-play.test.mjs` (asserção do markup do pódio/linha "you")

- [ ] **Step 1: Teste falhando** — em `tests/ranked-play.test.mjs`, asserir que o leaderboard renderiza um pódio para os 3 primeiros (ex.: elementos `.slot.s1/.s2/.s3`) e destaca a linha do usuário (`.board-you`). Rodar: `node --test tests/ranked-play.test.mjs` → FAIL.
- [ ] **Step 2:** Cartões de vidro: `.lab-choice`, o cartão de saldo (`fillRanked`) e os cartões/linhas do board viram superfícies de vidro (tokens da Task 2). Belt/badge art preservados.
- [ ] **Step 3:** Em `fillLeaderboard`, para os 3 primeiros renderizar o **pódio 3D** (ouro/prata/bronze, ♛ para `row.hat`) e abaixo as linhas foscas; manter a lógica existente de `board.rows`, `your_place`, `eligible`. CSS `.podium/.slot/.pill` do mock.
- [ ] **Step 4: Rodar o teste** → PASS. Verificar no browser (home do Ranked + leaderboard).
- [ ] **Step 5: Commit** — `git commit -m "feat(ranked): glass ranked home and 3D podium leaderboard"`

---

### Task 6: Ranked — quiz (palco do avatar + timer em anel + belts de vidro)

**Files:**
- Modify: `index.html` (`.belts/.belt`, `.quiz-timer`/`#ring`, `.tb-bar`, adicionar `.stage` do palco do avatar)
- Modify: `src/app.js` (`playRankedAttempt` — inserir o palco do avatar; `quizAvatar` reutilizado)
- Test: `tests/ranked-play.test.mjs`

- [ ] **Step 1: Teste falhando** — asserir que a tela de pergunta do Ranked contém o `<img class="quiz-avatar">` (hoje o Ranked não tem avatar). Rodar → FAIL.
- [ ] **Step 2:** Em `playRankedAttempt` (src/app.js), adicionar `${quizAvatar('thinking')}` num palco de vidro acima do código da rota — espelhando o padrão da Prática (`showCard`). Garantir que `quizAvatar` use os PNGs transparentes da Task 1 (`assets/avatar-thinking.png`).
- [ ] **Step 3:** Belts como **pílulas de vidro tingidas**: ajustar `.belts .belt` para o visual do mock (fosco, cor da belt preservada via `BELT_STYLE`), mantendo `.picked/.belt-correct/.belt-incorrect` (a animação de glow do #170 continua).
- [ ] **Step 4:** Timer em **anel**: restyle `.quiz-timer`/`#ring` para o anel do mock (conic-gradient dourado→vermelho no fim); manter o JS de contagem (`startCountdown`) intacto.
- [ ] **Step 5: Rodar o teste** → PASS. Verificar no browser: pergunta do Ranked com avatar, anel e belts de vidro; o cronômetro ainda conta e vira vermelho.
- [ ] **Step 6: Commit** — `git commit -m "feat(ranked): quiz with avatar stage, ring timer and glass belts"`

---

### Task 7: Ranked — feedback e resultado com avatar reagindo

**Files:**
- Modify: `src/app.js` (`showRankedFeedback`, `showRankedResult`, `showPromotionResult`)
- Modify: `index.html` (`.rq-verdict`, `.rq-worth`, `.sum`, `.rq-cmp`)
- Test: `tests/ranked-play.test.mjs`

- [ ] **Step 1: Teste falhando** — asserir que `showRankedFeedback` mostra `quiz-avatar` (happy quando correto, sad quando errado/timeout). Rodar → FAIL.
- [ ] **Step 2:** Em `showRankedFeedback`, adicionar `${quizAvatar(right ? 'happy' : 'sad')}` no palco de vidro; manter todo o texto de pontos/explicação/belt correta e as ramificações de promoção (`promoCorrect`/`promoLost`) intactas.
- [ ] **Step 3:** Estilizar veredito/worth/comparação e o resumo (`rankedSum`) como vidro (verde `--good`/vermelho `--bad`). `showRankedResult`: avatar idle no palco.
- [ ] **Step 4: Rodar o teste** → PASS. Verificar no browser: feedback correto/errado/timeout e a tela de resultado.
- [ ] **Step 5: Commit** — `git commit -m "feat(ranked): glass feedback and result with reacting avatar"`

---

### Task 8: Verificação completa da Fase 1

**Files:**
- Run only (sem edição de produção)

- [ ] **Step 1:** `node --test tests/*.test.mjs` → tudo verde (inclui `ranked-play`, `quiz-feedback-style`). Corrigir regressões.
- [ ] **Step 2:** Preview no browser do fluxo Ranked completo: dock, home, quiz (avatar+anel+belts), feedback (3 casos), resultado, leaderboard (pódio). Checar 320px sem overflow e `prefers-reduced-motion`.
- [ ] **Step 3:** Confirmar que Home/Prática/Perfil/Login ainda funcionam (não devem ter sido tocados além das fundações/dock) — sem telas quebradas pela mudança de fundo/tokens.
- [ ] **Step 4:** Tirar screenshots de antes/depois pra Renilson aprovar.
- [ ] **Step 5: Commit** (se houver ajustes) — `git commit -m "test(ranked): verify phase 1 glass redesign"`

---

### Task 9: Deploy na Azure staging

Renilson executa os passos `az`; esta task prepara e acompanha.

**Files:**
- Branch: `codex/ranked-mode` (integração que publica)

- [ ] **Step 1:** Abrir PR da Fase 1 (branch de trabalho → `codex/ranked-mode`), pedir aprovação do Renilson, mergear quando o CI passar.
- [ ] **Step 2:** Seguir `infra/azure/container-apps-app.md`: Renilson, no Cloud Shell, re-clona, rebuilda a venv, e dispara o publish (ambiente `publish`, aprovação dele). Lembrar: **mudar imagem/revisão** gera nova revisão do Container App (`az containerapp update --revision-suffix <word>`), não só restart.
- [ ] **Step 3:** Smoke test na URL de staging: fluxo Ranked renderiza o novo visual; `/health` 200; sem erro de console.
- [ ] **Step 4:** Registrar evidência (screenshot staging) e avisar o Renilson que está no ar.

---

## Follow-ups (planos separados, não nesta fase)

- **Fase 2 — resto do app:** aplicar o mesmo glass a Home, Prática (quiz/feedback/resultado), Perfil e Login. Mesma abordagem, telas diferentes.
- **Limpeza da codebase:** depois da Fase 2 — remover mocks obsoletos (`mockups/glassmorphism-review.html`, `feedback-demo.html`, `friendly-study.html`, `entry-navigation.html`, os recortes `mockups/redesign-assets/` se os assets de produção já existirem), CSS/JS morto em `index.html`/`app.js`, e consolidar tokens. Plano próprio com inventário do que é seguro remover.

## Verificação do plano (self-review)

- Cobre o escopo acordado (Ranked primeiro, stills): dock (T4), quiz (T6), feedback/resultado (T7), home/leaderboard (T5), fundações (T2), remoção do antigo (T3), assets (T1), verificação (T8), deploy (T9). ✓
- "Eliminar a versão que está" = T3 (overrides planos) + substituição in-place nas T4–T7. ✓
- Limpeza da codebase = follow-up explícito após a Fase 2. ✓
- Sem placeholders de lógica: as regras do Ranked e o i18n são preservados; strings novas via `t()` + ES.
