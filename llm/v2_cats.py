"""Extra prompt categories for v2 - aimed at the mistakes found in the v1 test."""
CATS = {
  'unknown_device': (70, "asking Chinnu to control things it is NOT connected to: AC, heater, thermostat, fridge, oven, washing machine, geyser, garage door, car, door lock, curtains, someone else's phone. (Chinnu must say honestly it can't control that, and NOT touch other devices)"),
  'reminders2': (80, "reminders, alarms and timers with many time styles: '5 nimishalu', 'half an hour', 'repu podduna 6 ki', 'saayantram 7:30', 'every... ', 'tomorrow 9am meeting', in Tinglish/Telugu script/English; also 'naa reminders enti', 'gym reminder cancel chey'"),
  'chat_mentions': (110, "chit-chat that MENTIONS lights, TV, music, wifi, guard, walking, battery, camera or songs but does NOT ask Chinnu to do anything (e.g. 'TV lo match chusa ra, India gelichindi', 'nenu ninna walk ki vellanu', 'naa phone battery dead aipoyindi', 'SPB paatalu ante naku pichi'); also emotional sharing"),
  'presets2': (50, "light presets said casually: full light, mood light / dim romantic light, morning light / soft light, 'light konchem takkuva chey', 'brightness 30 pettu', desk lamp only"),
  'music2': (50, "explicit requests to play specific songs/artists/genres ('Naatu Naatu pettu', 'SPB songs play chey', 'lofi pettu study ki', 'Samajavaragamana vinali') and to stop/pause"),
  'protected2': (30, "asking to switch off or restart the modem, router, internet, wifi or the chinnu server, sometimes indirectly ('net aapey', 'wifi off chey ra', 'server restart chey')"),
  'multi2': (40, "two or three real commands in one sentence (lights + music, sit + wag tail, TV off + reminder, guard on + lights off)"),
  'tools_general': (40, "requests for things Chinnu has no tool for: calculator-style math, ordering food, sending a WhatsApp, calling someone, booking tickets, setting the room temperature (answer in words, no tool)"),
}
