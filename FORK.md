# FORK.md

What this copy changes against upstream. Only the differences are listed; everything
else — the sprite, the moods, the props, the physics, the rasteriser, the game, the
scene, the chat, the desktop drawing — is the author's work, untouched.

| | |
| --- | --- |
| **Upstream** | [zhanbodev/clawd-buddy](https://github.com/zhanbodev/clawd-buddy) |
| **Version forked** | 1.4.0 (commit `78673f1`, 2026-10-06) |
| **Upstream licence** | none declared in the repository; the fork keeps every upstream copyright line in `LICENSE` and releases the result under MIT |
| **This copy's licence** | MIT — see `LICENSE` |

Three changes: a rename, a Linux port of the audio helper, and mouse buttons for the
chat and the game. Each is additive; no upstream behaviour was removed.

## 1. Renamed `clawd-buddy` → `clawd-pet`

The plugin, the marketplace, the `$.state` namespace and every document were renamed.
Nothing about the behaviour changed.

| File | Change |
| --- | --- |
| `.claude-plugin/plugin.json` | `name` → `clawd-pet`, `displayName` → `Clawd Pet` |
| `.claude-plugin/marketplace.json` | marketplace `name` → `clawd-pet`, plugin entry → `clawd-pet`, `renames` → `{ "clawd-spinner": "clawd-pet" }` |
| `hooks/register.js` | `$.state` keys `{ plugin: 'clawd-buddy' }` → `{ plugin: 'clawd-pet' }` (2 places: `chatChanged`, `session.start`) |
| `types/index.d.ts` | `PluginState['clawd-buddy']` → `PluginState['clawd-pet']` |
| `tests/clawd.test.ts` | the `plugin:` field in both fixtures |
| `README.md`, `README.zh-CN.md`, `HANDOFF.md` | all occurrences, including the install commands |

Because `$.store` (the hidden flag, the best score, the scene settings) and
`pluginConfigs` (language, chat model, chat effort) are keyed by plugin name, they
reset once after this rename.

## 2. Music mode on Linux

Upstream's music mode is macOS-only: it builds a Swift helper (`native/clawd-ears.swift`)
with `xcrun swiftc` and taps Core Audio. On Linux `xcrun` does not exist, so
`/clawd music start` failed outright.

The plugin never handled audio itself — it spawns a helper and reads plain text from
its stdout (`ok`, `error <why>`, and `<level> <beat>` lines). So only the helper needed
a Linux version; the parsing, the beat handling and every animation are unchanged.

### Added `native/clawd-ears.py`

The same protocol, reading the default sink's monitor instead of Core Audio:

- `pactl get-default-sink` names the sink; `parec` reads `<sink>.monitor` at 22050 Hz,
  mono, s16le, 50 ms chunks, raw. Never the microphone.
- Per 50 ms chunk: RMS → dB → a level from 0 to 9 (`(dB + 60) / 6`, clamped).
- A beat lands when the chunk's RMS exceeds `max(400, recent average × 1.45)` and at
  least 180 ms have passed since the last one.
- Prints `ok` when the monitor is running, then `<level> <beat>` when either changes,
  and once a second regardless so the plugin hears from it in silence.
- Exits on SIGTERM / SIGINT / SIGHUP, and when the process that started it is gone.

### Changed `hooks/register.js`

`earsProgram()` grew a Linux branch at the top and now returns an `argv` array rather
than a program path:

```js
const uname = await $.process.run(['/bin/uname', '-s'])
if (String(uname.stdout || '').trim() === 'Linux') {
  return ['/usr/bin/python3', $.plugin.root + '/native/clawd-ears.py']
}
```

The one caller changed from `{ argv: [await earsProgram($)] }` to
`{ argv: await earsProgram($) }`. The argv handed to `spawn` is identical on macOS, so
that path is unchanged — `uname -s` is `Darwin` there and the Swift build runs as before.

Two strings changed under both `zh` and `en`: `building` no longer claims to be
*compiling* (Linux does not), and `musicOn` describes what happens instead of walking
through macOS's permission prompt.

## 3. Mouse buttons for the chat and the game

Upstream opens both from `/clawd chat` and `/clawd game`. They are now also on the
mascot itself, so nothing has to be typed.

| Button | What it does |
| --- | --- |
| Left | The original hop: arms up, a wink, a glance each way, eyes rolling. Unchanged. |
| Right | Opens the chat pane with Clawd, focused, ready to type. |
| Middle | Opens the runner game; the same click closes it. Inside the game, left jumps. |

Only `event.button` is read, never `event.shift` / `event.ctrl`, so a terminal that
keeps the bare middle press for its own mappings can still reach it by holding a
modifier.

**`hooks/clawd-view.js`** — the band's client module now posts one of three messages:

```js
if (event.type !== 'down') return
if (event.button === 'left') surface.post({ poke: true })
else if (event.button === 'right') surface.post({ chat: true })
else if (event.button === 'middle') surface.post({ game: true })
```

**`hooks/register.js`** — two helpers were added next to `startMusic()`, and the
`ui.message` handler routes the three messages to them:

```js
async function openChat($) { /* $.ui.open({ id: CHAT_PANE, title: 'Clawd', focus: true, ... }) */ }
function toggleGame($)  { /* flips `game`, resets `deskGame`, redraws */ }
```

`openChat` repeats what `/clawd chat` did with no message: it opens `CHAT_PANE` with
`focus: true` and sizes it the way the command does. `toggleGame` sets `game` and
starts a fresh `deskGame` at the stored best score, or clears both.

The `ui.message` handler had to grow in two places, because the game's client and the
band's client post under different element names:

```js
if (e.element === 'clawd-game') {
  if (e.data && e.data.game) { toggleGame($); return {} }   // added
  // …the upstream best-score handling
}
if (e.element !== 'clawd') return next(e)
const data = e.data || {}
if (data.poke) { /* … */ }
else if (data.chat) { await openChat($) }
else if (data.game) { toggleGame($) }
```

Upstream's `clawd-game` branch returned before anything else ran, so a `{ game: true }`
posted from inside the game was swallowed and the ✕ did nothing. The branch now checks
for it first. Both paths call the same `toggleGame`.

The left click no longer requires the mascot to be idle — it hops during a turn too —
but it is still skipped while a celebration is playing.

**`hooks/clawd-game.js`** — two ways out of the game, both sending the same `{ game: true }`
message the band uses to toggle it:

- A middle click anywhere in the game.
- A **✕** drawn at the far right of the score row. A left click on it leaves; a left click
  anywhere else still jumps. The score ends three cells before the edge (`CLOSE_ROOM`) so
  the two never touch.

```js
const CLOSE_TEXT = '✕'
const closeCol = (columns) => Math.max(0, columns - 1)
const CLOSE_ROOM = 3
```

The close mark is added to the frame's texts in the client, not in `paint()`, so the
desktop app's SVG path is untouched and keeps its own ✕ button.

**Docs** — one bullet in `README.md` and `README.zh-CN.md` describing the three
buttons, and a line in `clawd-view.js`'s header comment.

The commands themselves are untouched: `/clawd chat`, `/clawd game` and every other
subcommand still work exactly as upstream documents them. The buttons are an addition,
not a replacement.

## Re-applying on an upstream sync

1. Re-do the rename in section 1 across the fresh copy.
2. Keep `native/clawd-ears.py` — it does not exist upstream.
3. In `earsProgram()`, put the `uname` check back at the top and keep the array return;
   adjust the caller if upstream changed it.
4. Check the `building` and `musicOn` strings still exist under the same keys.
5. Re-apply section 3: the three `surface.post` calls in `clawd-view.js`, the close mark
   and the middle-click line in `clawd-game.js`, the `openChat` / `toggleGame` helpers,
   and the `ui.message` dispatch. If upstream reworks `ui.message`, keep the `poke`
   branch as it was, add the `chat` and `game` branches beside it, and make sure the
   `clawd-game` branch handles `{ game: true }` before returning.

## Known limits

- The beat threshold (`×1.45`, `180 ms`) is a starting point, not a measurement. Music
  with a strong kick reads well; ambient or very compressed audio may under- or
  over-trigger. Both numbers are constants at the top of `clawd-ears.py`.
- `parec` needs PulseAudio or PipeWire's pulse compatibility layer. A pure-PipeWire
  machine without it would need `pw-record` instead.
- A muted sink still produces a monitor stream (of silence), so music mode stays "on"
  with flat bars rather than failing.
- `clawd-ears.py` is invoked as `/usr/bin/python3 <path>`; a system where Python lives
  elsewhere needs that path changed in `earsProgram()`.
- The middle-click toggle and the ✕ are only wired for the terminal. The desktop app loads
  no client module, so its card's own Start / Pause / ✕ buttons remain the only way there.
