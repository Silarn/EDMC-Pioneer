# Pioneer plugin for [EDMC](https://github.com/Marginal/EDMarketConnector/wiki)

Pioneer is a tool for explorers to have an at-a-glance view of key system information. It will predict a total possible
as well as current value of all exploration data in a system. Due to limitations of EDMC journal data parsing,
Pioneer works best on newly visited and unscanned systems. However, it can provide a rough calculation for systems
when data is downloaded from a nav beacon. It also provides the option to get system data from EDSM to fill out missing
information.


### Value Calculations
Value calculations include whether a body was previously discovered or mapped, the terraforming bonus (as a likely
range), and any 'first fully scanned / mapped' bonuses you may qualify for as well as the bonus on Odyssey / 4.0+
clients.

Pioneer will display a number of things. Based on a configurable value, the top of the pane will display high value
mappable bodies. It can also display any bodies with biological signals. Following this is an optional scrollbox with
a detailed breakdown of every system body.

At the top is an esitmate of the main star value including the honk bonus provided by all other bodies.
This is followed by a list of scanned bodies, their calculated current and maximum values, and the honk
bonus they provide. At the bottom of the list, it will include any additional bonuses for being the first to fully map
or scan the system. Finally, the overall current (based on scan and map status) and maximum (if fully mapped) values are
displayed at the bottom of the pane.

Star and body types are fully parsed and displayed as well as flags for terraforming candidates, fully scanned and
mapped systems, and whether you've 'honked' yet.

### EDSM Integration
The latest version has added the ability to pull body data from EDSM. This can be done on system jump or limited to only
systems where a 'honk' indicates it was already fully scanned. (This should cover pre-explored core systems and those
which were previously visited and fully scanned.)

## Requirements
* EDMC version 5 and above

## Installation
* Download the [latest release]
* Extract the `.zip` archive that you downloaded into the EDMC `plugins` folder
  * This is accessible via the plugins tab in the EDMC settings window
* Start or restart EDMC to register the new plugin

## Acknowledgements

Core idea and some base calculations originate from the [Economical Cartographics plugin][EcCon] by Nils Steinger.

Value calculations based on [information by MattG](https://forums.frontier.co.uk/threads/exploration-value-formulae.232000/).

## Roadmap

The overall goal is to make this a valuable tool for explorers in Elite Dangerous, highlighting valuable bodies in a
reasonably compact format.

Any reasonably useful info that I can display succinctly could be added. I'm considering a separate plugin to evaluate
possible value ranges for exobiology signals - as well as a progress display on scanned samples with a final analysed
value including the footfall bonus.

One possible project would be to calculate the habitable zone and attempt to estimate the terraform bonus based on that
range. My assumption is that the bonus is highest at the center of this zone. This hasn't been confirmed, but I will use
this to test better value estimates.

Suggestions and requests are welcome.

## License

[Pioneer plugin][Pioneer] Copyright © 2023 Jeremy Rimpo

Licensed under the [GNU Public License (GPL)][GPLv2] version 2 or later.

[EDMC]: https://github.com/EDCD/EDMarketConnector/wiki
[Pioneer]: https://github.com/Silarn/EDMC-Pioneer
[EcCon]: https://github.com/n-st/EDMC-EconomicalCartographics
[latest release]: https://github.com/Silarn/EDMC-Pioneer/releases/latest
[GPLv2]: http://www.gnu.org/licenses/gpl-2.0.html
