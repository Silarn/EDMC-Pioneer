# Economical Cartographics plugin for [EDMC](https://github.com/Marginal/EDMarketConnector/wiki)

This plugin helps explorers find high-value planets in Elite: Dangerous.

It analyses the data returned by the Full-System Scanner and lists planets that
are worth mapping with a [Detailed Surface Scanner][DSS], i.e. those whose
estimated scan reward (based on type, terraformability and first-discovery
state) exceeds a given value.

The plugin will start out by showing "EC: no scans yet", and will start
displaying planet information in that line once you scan at least one planet
with the FSS.  
"Worthwhile" planets (value >= 300 kCr) will be listed explicitly with their
value and distance from the main star, "cheap" planets will simply be added to
a counter at the end of the line.

**Note:** The plugin is not quite complete yet (it could use a layout polish,
and a proper configuration menu), but is usable in its basic functions.

## Installation

* On EDMC's Plugins settings tab press the “Open” button. This reveals the `plugins` folder where EDMC looks for plugins.
* Download the [latest release](https://github.com/n-st/EDMC-EconomicalCartographics/releases/latest).
* Open the `.zip` archive that you downloaded and move the `EDMC-EconomicalCartographics` folder contained inside into the `plugins` folder.

You will need to re-start EDMC for it to notice the new plugin.

## Acknowledgements

Plugin code and description partially based on the [Habitable Zone plugin][HabZone] by Jonathan Harris.

Value calculations based on [information by MattG](https://forums.frontier.co.uk/threads/exploration-value-formulae.232000/).

## License

[Habitable Zone plugin][HabZone] Copyright © 2017 Jonathan Harris.  
Modified into the Economical Cartographics plugin by [n-st](https://github.com/n-st).

Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.

[DSS]: http://elite-dangerous.wikia.com/wiki/Detailed_Surface_Scanner
[HabZone]: https://github.com/Marginal/HabZone
