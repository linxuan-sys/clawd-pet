// The surface module that shows the mascot in the band above the prompt. The hooks module works
// out every frame and hands it over as props: gridRuns' data, each terminal row's runs of cells
// as { text, color, backgroundColor }. Drawn here, in a Client's region, the mascot holds the
// pointer: a press on it can't start a text selection, so it never gets copied. Left click
// makes the mascot hop; right click opens the chat with it; middle click opens the runner game.
// Only the button is read, never the modifiers, so a terminal that reserves the bare press for
// itself can still reach it with one held.
export default function ClawdView(props, surface) {
  const { Box, Text } = surface.elements
  surface.onPointer((event) => {
    if (event.type !== 'down') return
    if (event.button === 'left') surface.post({ poke: true })
    else if (event.button === 'right') surface.post({ chat: true })
    else if (event.button === 'middle') surface.post({ game: true })
  })
  const { columns, rows } = props
  return Box({
    flexDirection: 'column',
    width: columns,
    flexShrink: 0,
    children: rows.map((runs) =>
      Box({
        flexDirection: 'row',
        width: columns,
        flexShrink: 0,
        children: runs.map(({ text, color, backgroundColor }) => {
          if (color === null) return Box({ width: text.length, height: 1, flexShrink: 0 })
          return Text(backgroundColor === null ? { children: [text], color } : { children: [text], color, backgroundColor })
        }),
      }),
    ),
  })
}
