Description
------------------

Buffer Scroll is a simple [Sublime Text](http://www.sublimetext.com/ ) plug-in which remembers and restores the scroll, cursor positions, also the selections, marks, bookmarks, foldings, selected syntax and optionally the color scheme.

Also, via preferences, allows to enable syncing of scroll, bookmarks, marks and folds between cloned views.

Syncing features are disabled by default. You need to enable these via the preferences. Main menu -> Preferences -> Package Settings -> BufferScroll -> Settings Default.
You may want to copy and paste your edited preferences to "Settings Users" located under the same sub-menu. To keep your preferences between updates.

Requested by Kensai this package now provides "typewriter scrolling":  The line you work with is automatically the vertical center of the screen.

<img src="http://dl.dropbox.com/u/9303546/SublimeText/BufferScoll/sync-scroll.png" border="0"/>

Installation
------------------

Install this repository via "Package Control" http://wbond.net/sublime_packages/package_control

Source-code
------------------

https://github.com/SublimeText/BufferScroll

Bugs
------------------

For some reason sublime API is not restoring scroll of xml/html documents, including: xml, tpl, html, xhtml
See and vote: http://www.sublimetext.com/forum/viewtopic.php?f=3&t=6237&start=0

Forum Thread
------------------

http://www.sublimetext.com/forum/viewtopic.php?f=5&t=3503

License
------------------

See license.txt