import sublime, sublime_plugin
from os.path import exists, normpath
from hashlib import sha1

try:
	from cPickle import load, dump
except:
	sublime.error_messsage('BufferScroll: Unable to load module cPickle.')

debug = False

# open

database = sublime.packages_path()+'/User/BufferScroll.bin'
if exists(database):
	try:
		db = load(file(database, 'rb'));
	except:
		db = {}
else:
	db = {}

	# upgrade
	from os import remove, rename
	try:
		remove(sublime.packages_path()+'/User/BufferScroll.sublime-settings')
	except:
		pass
	try:
		rename(sublime.packages_path()+'/User/BufferScrollUser.sublime-settings',
		       sublime.packages_path()+'/User/BufferScroll.sublime-settings')
	except:
		pass

# settings

s = sublime.load_settings('BufferScroll.sublime-settings')
class Pref():
	def load(self):
		Pref.remember_color_scheme 	= s.get('remember_color_scheme', False)
		Pref.current_view						= -1
		version                     = 6
		version_current             = s.get('version')
		if version_current != version:
			s.set('version', version)
			db = {}
			sublime.save_settings('BufferScroll.sublime-settings')

Pref().load()
s.add_on_change('remember_color_scheme', lambda:Pref().load())

class BufferScroll(sublime_plugin.EventListener):

	# restore on load for new opened tabs or previews.
	def on_load(self, view):
		self.restore(view, 'on_load')

	# restore on load for cloned views
	def on_clone(self, view):
		self.restore(view, 'on_clone')

	# the application is not sending "on_close" event when closing
	# or switching the projects, then we need to save the data on focus lost
	def on_deactivated(self, view):
		self.save(view, 'on_deactivated')

	# track the current_view. See next event listener
	def on_activated(self, view):
		if view.file_name() and not view.settings().get('is_widget'):
			Pref.current_view = view.id() # this id is not unique

	# save the data when background tabs are closed
	# these that don't receive "on_deactivated"
	def on_close(self, view):
		# current_view will receive event on_deactivated ( when closing )
		# which provides more data than on_close
		# for example a "get_view_index" ..
		if Pref.current_view != view.id():
			self.save(view, 'on_close')

	# save data for focused tab when saving
	def on_post_save(self, view):
		self.save(view, 'on_post_save')

	# saving
	def save(self, view, where):
		if not view.file_name() or view.settings().get('is_widget'):
			return

		id, index = self.view_id(view)

		if debug:
			print '-----------------------------------'
			print 'saving from '+where
			print view.file_name()
			print 'id '+id
			print 'position in tabbar '+index


		# creates an object for this view, if it is unknow to the package
		if id not in db:
			db[id] = {}
			if 'l' not in db[id]:
				db[id]['l'] = {}

		# if the result of the new collected data is different
		# from the old data, then will write to disk
		old_db = dict(db[id])

		# if the size of the view change outside the application skip restoration
		# if not we will restore folds in funny positions, etc...
		db[id]['id'] = long(view.size())

		# scroll
		if int(sublime.version()) >= 2151:
			# save the scroll with "index" as the id ( usefull for cloned views )
			db[id]['l'][index] = view.viewport_position()
			# also save as default if no exists
			if '0' not in db[id]['l']:
				db[id]['l']['0'] = view.viewport_position()

		# selections
		db[id]['s'] = [[item.a, item.b] for item in view.sel()]

		# # marks
		db[id]['m'] = [[item.a, item.b] for item in view.get_regions("mark")]

		# # bookmarks
		db[id]['b'] = [[item.a, item.b] for item in view.get_regions("bookmarks")]

		# previous folding save, to be able to refold
		if 'f' in db[id] and list(db[id]['f']) != []:
			db[id]['pf'] = list(db[id]['f'])

		# folding
		if int(sublime.version()) >= 2167:
			db[id]['f'] = [[item.a, item.b] for item in view.folded_regions()]
		else:
			folds = view.unfold(sublime.Region(0, view.size()))
			db[id]['f'] = [[item.a, item.b] for item in folds]
			view.fold(folds)

		# color_scheme http://www.sublimetext.com/forum/viewtopic.php?p=25624#p25624
		if Pref.remember_color_scheme:
			db[id]['c'] = view.settings().get('color_scheme')

		# syntax
		db[id]['x'] = view.settings().get('syntax')

		# write to disk only if something changed
		if old_db != db[id]:
			if debug:
				print id
				print db[id];
			sublime.set_timeout(lambda:self.write(), 0)

		del old_db

	def view_id(self, view):
		if not view.settings().has('buffer_scroll_name'):
			view.settings().set('buffer_scroll_name', sha1(normpath(view.file_name().encode('utf-8'))).hexdigest()[:8])
		return (view.settings().get('buffer_scroll_name'), self.view_index(view))

	def view_index(self, view):
		window = view.window();
		if not window:
			window = sublime.active_window()
		index = window.get_view_index(view)
		if index and index != (0,0) and index != (0,-1) and index != (-1,-1):
			return str(index)
		else:
			return '0'

	def write(self):
		if debug:
			print 'writting to disk'
		dump(db, file(database, "wb"))

	def restore(self, view, where):
		if not view.file_name() or view.settings().get('is_widget'):
			return

		if view.is_loading():
			sublime.set_timeout(lambda: self.restore(view), 100)
		else:

			id, index = self.view_id(view)

			if debug:
				print '-----------------------------------'
				print 'restoring from '+where
				print view.file_name()
				print 'id '+id
				print 'position in tabbar '+index

			if id in db:

				# if the view changed outside of the application, don't restore folds etc
				if db[id]['id'] == long(view.size()):

					# fold
					rs = []
					for r in db[id]['f']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.fold(rs)

					# selection
					if len(db[id]['s']) > 0:
						view.sel().clear()
						for r in db[id]['s']:
							view.sel().add(sublime.Region(int(r[0]), int(r[1])))

					# marks
					rs = []
					for r in db[id]['m']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.add_regions("mark", rs, "mark", "dot", sublime.HIDDEN | sublime.PERSISTENT)

					# bookmarks
					rs = []
					for r in db[id]['b']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.add_regions("bookmarks", rs, "bookmarks", "bookmark", sublime.HIDDEN | sublime.PERSISTENT)

					# color scheme
					if Pref.remember_color_scheme and 'c' in db[id] and view.settings().get('color_scheme') != db[id]['c']:
						view.settings().set('color_scheme', db[id]['c'])

					# syntax
					if view.settings().get('syntax') != db[id]['x']:
						view.settings().set('syntax', db[id]['x'])

				# scroll
				if int(sublime.version()) >= 2151:
					if index in db[id]['l']:
						view.set_viewport_position(tuple(db[id]['l'][index]), False)
					else:
						view.set_viewport_position(tuple(db[id]['l']['0']), False)

class BufferScrollForget(sublime_plugin.ApplicationCommand):
	def run(self, what):
		if what == 'color_scheme':
			sublime.active_window().active_view().settings().erase('color_scheme')

class BufferScrollReFold(sublime_plugin.WindowCommand):
	def run(self):
		view = sublime.active_window().active_view()
		if view:
			id, index = BufferScroll().view_id(view)
			if id in db:
				if 'pf' in db[id]:
					rs = []
					for r in db[id]['pf']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.fold(rs)