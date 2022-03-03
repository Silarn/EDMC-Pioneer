# Pioneer plugin for [EDMC](https://github.com/Marginal/EDMarketConnector/wiki)

Pioneer (System Value) aims to calculate the overall value of a newly scanned system. Due to limitations of journal
data, previously visited or 'unscannable' systems are difficult to calculate. This calculation includes whether a
body was previously discovered or mapped, the terraforming bonus (as a likely range), and any 'first fully scanned /
mapped' bonuses you may qualify for.

Pioneer will display a number of things. Based on a configurable value, the top of the pane will display high value
mappable bodies. This is followed by a list of scanned bodies, their calculated current and maximum values, the honk
bonus they provide, bonuses for being the first to fully map or scan the system, and a calculation for the main star
value. Finally, the overall current (based on scan and map status) and maximum (if fully mapped) values are displayed
at the bottom of the pane.

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

Currently no real body data is preserved except for the overall value and distance of each body. My plan is to extend
this to track more body data so that I can display body type, landability, and atmospherics in order to better indicate
interesting bodies, such as a chance for biological samples.

I also intend to offer more configuration options, like an ability to hide the scroll box of individual body values.

## License

[Pioneer plugin][Pioneer] Copyright © 2022 Jeremy Rimpo

Licensed under the [GNU Public License (GPL)][GPLv2] version 2 or later.

[EDMC]: https://github.com/EDCD/EDMarketConnector/wiki
[Pioneer]: https://github.com/Silarn/EDMC-Pioneer
[EcCon]: https://github.com/n-st/EDMC-EconomicalCartographics
[latest release]: https://github.com/Silarn/EDMC-Pioneer/releases/latest
[GPLv2]: http://www.gnu.org/licenses/gpl-2.0.html
