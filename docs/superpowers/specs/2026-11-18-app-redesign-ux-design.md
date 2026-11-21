# Redesign do app — design e UX (mock aprovado)

> Complementa o [plano de glassmorphism](2026-11-18-glassmorphism-redesign-plan.md).
> Aquele doc trata dos tokens de vidro, som e animação das belts; **este** registra
> a direção de UX e a cobertura do app inteiro que o dono aprovou no mock geral.

Fonte visual (verdade): `mockups/app-redesign-mock.html` — mock de revisão, dados
fictícios, servido localmente. O app de produção **não** foi alterado.

## Intenção e direção acordada

O dono quer repaginar o Sort Lab com estética **glassmorphism "trivia game"**
(referência: shot "Glassmorphism Trivia Game UI" no Dribbble), mas **mantendo a
marca UPS**: paleta Saddle Brook Twilight (marrom `#38261b` / dourado `#f4bd38` /
branco quente), tipografia Nunito e o **significado das cores das belts**
(`src/belts.js`). O fundo vira um degradê escuro "twilight" com orbes de luz;
cartões, pílulas e dock são de vidro fosco (`backdrop-filter`).

Decisões travadas com o dono (2026-11-18):
- Paleta: **marrom/dourado + vidro** (on-brand), não o roxo da referência.
- Escopo do mock: **app inteiro**.
- Avatar no quiz: **modelo 3D animado** (não still recortado).
- Badges: emblema **sem fundo**.

## Abordagem

Estender o diretório de mocks existente, sem mexer no app. O mock geral é uma
galeria de 9 telas em molduras de celular, cada uma com o mesmo sistema de vidro.
Reaproveita os tokens de `mockups/glassmorphism-review.html`, o avatar 3D de
`mockups/design-library/blender-avatar/embed.html` e os badges transparentes de
`mockups/design-library/badges/`. É protótipo de aparência, não pacote de
componentes de produção.

## Escopo (telas cobertas)

1. Entrada/Login · 2. Home (membro) · 3. Prática — Quiz · 4. Prática — Feedback ·
5. Ranked — Início · 6. Ranked — Quiz · 7. Ranked — Resultado · 8. Leaderboard ·
9. Perfil. (Ranked segue `src/app.js`; Prática segue o fluxo atual.)

## Mudanças de UX (por área, aprovadas)

- **Navegação / dock:** dock flutuante de vidro, item ativo em pílula dourada com
  brilho. Convidado vê só Home + Prática; Ranked com cadeado pra convidado.
- **Entrada / login:** uma tela de boas-vindas única — marca grande, campo de ID
  num card fosco, dois botões (Entrar com ID / Continuar como convidado). Deixa
  explícito que Ranked precisa de login.
- **Quiz (unifica Prática e Ranked):** topo com "Pergunta X de 15" + **cronômetro
  em anel** que fica vermelho no fim; **palco de vidro com o avatar 3D animado**
  reagindo (idle/thinking/correct/incorrect); código da rota em card de vidro;
  belts como **pílulas foscas tingidas da cor real** (significado preservado),
  2 colunas; feedback com brilho verde/vermelho e o avatar reagindo.
- **Home:** banner da temporada (arte do boné UPS), chip de saldo/rank, dois CTAs
  grandes (Praticar / Ranked), card de mudanças de sort.
- **Leaderboard:** pódio 3D top-3 (♛ ganhadores do boné), linhas foscas, **sua
  linha destacada**; "sua posição" quando fora da lista.

## Avatar e badges (assets)

- **Avatar:** no mock usa o visualizador 3D `embed.html` (Three.js + o GLB
  aprovado), que já aceita `?state=idle|thinking|correct|incorrect`, tem fundo
  transparente e respeita `prefers-reduced-motion` (checkbox "still"). Para
  **produção**, decidir entre: (a) embutir esse 3D nas telas de quiz, ou (b)
  stills PNG transparentes re-renderizados do `.blend` com `film_transparent`
  (o caminho limpo; o binário `blender` da máquina está quebrado hoje, apontando
  pra um `Blender.app` inexistente). Os recortes em `mockups/redesign-assets/
  avatar/` foram um paliativo e **não** devem ir pra produção.
- **Badges:** usar os PNGs transparentes de `mockups/design-library/badges/`
  (`iron/bronze/silver/gold/challenger-concept-v1.png`), não os JPG de fundo
  branco em `assets/badge-*.jpg`.

## Preservado / restrições

- Marca UPS (marrom/dourado), significado das cores das belts, e as **regras do
  Ranked** (15 perguntas, 10s, pontos/cap/promoção/quit) — o redesign é só visual.
- Nenhuma mudança no app de produção neste trabalho. Acessibilidade: foco visível,
  reduzir movimento, contraste — a validar na implementação.

## Perguntas em aberto

1. Avatar em produção: 3D embutido vs. stills transparentes? (peso de WebGL por
   tela vs. simplicidade). O mock roda 4 contextos WebGL de uma vez; aceitável
   pra revisão, a medir pra produção.
2. Adoção: trocar tudo de uma vez ou por fatias (ex.: Ranked primeiro)?
3. Tema: só o twilight escuro, ou manter também um tema claro de vidro?
4. Relação com o [plano de glass](2026-11-18-glassmorphism-redesign-plan.md): este
   mock vira a referência visual dele, ou consolidamos os dois num plano só?

## Verificação (feita no mock)

As 9 telas abertas no navegador (desktop e largura de celular); os 4 avatares 3D
carregam e animam pelo servidor local; badges transparentes conferidos no saldo
do Ranked e no perfil; sem erros no console da página. O 3D só carrega servido
por HTTP (imports de módulo + `.glb`), não via `file://`.
