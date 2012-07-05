import sublime, sublime_plugin
from os.path import lexists, normpath
from hashlib import sha1
from gzip import GzipFile
import thread
from cPickle import load, dump
import time

debug = False

# open

db = {}

database = sublime.packages_path()+'/../Settings/BufferScroll.bin.gz'
if lexists(database):
	try:
		gz = GzipFile(database, 'rb')
		db = load(gz);
		gz.close()
	except:
		db = {}
else:

	# upgrade
	from os import remove

	# database in User package -> Database in Settings dir
	if lexists(sublime.packages_path()+'/User/BufferScroll.bin.gz'):
		try:
			gz = GzipFile(sublime.packages_path()+'/User/BufferScroll.bin.gz')
			db = load(gz)
			gz.close()
			remove(sublime.packages_path()+'/User/BufferScroll.bin.gz')
		except:
			db = {}

	# from version 6 to 7
	if lexists(sublime.packages_path()+'/User/BufferScroll.bin'):
		try:
			db = load(file(sublime.packages_path()+'/User/BufferScroll.bin', 'rb'));
		except:
			db = {}
		try:
			remove(sublime.packages_path()+'/User/BufferScroll.bin')
		except:
			pass


# settings

s = sublime.load_settings('BufferScroll.sublime-settings')
class Pref():
	def load(self):
		Pref.remember_color_scheme 	              = s.get('remember_color_scheme', False)
		Pref.synch_bookmarks 				              = s.get('synch_bookmarks', False)
		Pref.synch_marks 						              = s.get('synch_marks', False)
		Pref.synch_folds 						              = s.get('synch_folds', False)
		Pref.synch_scroll 					              = s.get('synch_scroll', False)
		Pref.typewriter_scrolling									= s.get('typewriter_scrolling', False)
		Pref.current_view						              = -1
		Pref.writing_to_disk				              = False

		Pref.synch_data_running										= False
		Pref.synch_scroll_running 								= False
		Pref.synch_scroll_last_view_id						= 0
		Pref.synch_scroll_last_view_position			= 0
		Pref.synch_scroll_current_view_object 		= None
		version                                   = 7
		version_current                           = s.get('version')
		if version_current != version:
			s.set('version', version)
			sublime.save_settings('BufferScroll.sublime-settings')

Pref = Pref()
Pref.load()
s.add_on_change('reload', 	lambda:Pref.load())

class BufferScroll(sublime_plugin.EventListener):

	# restore on load for new opened tabs or previews.
	def on_load(self, view):
		self.restore(view, 'on_load')
# print 'on_load'
# print view.buffer_id()

# for window in sublime.windows():
# 	for _view in window.views():
# 		if not _view.is_loading() and _view.file_name() == view.file_name() and view.buffer_id() != _view.buffer_id():
# 			print 'clone found'
# 			print 'previous id = '
# 			print _view.buffer_id()
# 			print 'currnet id'
# 			print view.buffer_id()

# 			previous_window = view.window();
# 			if not previous_window:
# 				previous_window = sublime.active_window()
# 			index = previous_window.get_view_index(view)
# 			previous_window.focus_view(view)

# 			clone_window = _view.window();
# 			if not clone_window:
# 				clone_window = sublime.active_window()
# 			clone_window.focus_view(_view)
# 			clone_window.run_command('clone_file')
# 			previous_window.set_view_index(clone_window.active_view(), 0, 0)
# 			previous_window.set_view_index(clone_window.active_view(), index[0], index[1])
# 			return
	# restore on load for cloned views
	def on_clone(self, view):
		self.restore(view, 'on_clone')

	# the application is not sending "on_close" event when closing
	# or switching the projects, then we need to save the data on focus lost
	def on_deactivated(self, view):
		#print 'on_deactivated'
		self.save(view, 'on_deactivated')
		# synch bookmarks, marks, folds ( not scroll )
		self.synch(view)

	# track the current_view. See next event listener
	def on_activated(self, view):
		if view.file_name() and not view.settings().get('is_widget'):
			#print 'on_activated'
			Pref.current_view = view.id() # this id is not unique
			Pref.synch_scroll_current_view_object = view

	# save the data when background tabs are closed
	# these that don't receive "on_deactivated"
	def on_close(self, view):
		# current_view will receive event on_deactivated ( when closing )
		# which provides more data than on_close
		# for example a "get_view_index" ..
		if Pref.current_view != view.id():
			self.save(view, 'on_close')

	# save data for focused tab when saving
	def on_pre_save(self, view):
		self.save(view, 'on_pre_save')

	# typewriter scrolling
	def on_modified(self, view):
		if Pref.typewriter_scrolling and len(view.sel()) == 1 and not view.settings().get('is_widget') and not view.is_scratch():
			window = view.window();
			if not window:
				window = sublime.active_window()
			view = window.active_view()
			view.show_at_center(view.sel()[0].end())

	# saving
	def save(self, view, where = 'unknow'):
		if view is None or not view.file_name() or view.settings().get('is_widget'):
			return

		if view.is_loading():
			sublime.set_timeout(lambda: self.save(view, where), 100)
		else:

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

			# marks
			db[id]['m'] = [[item.a, item.b] for item in view.get_regions("mark")]

			# bookmarks
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
			if old_db != db[id] or where == 'on_deactivated':
				if debug:
					print id
					print db[id];
				if not Pref.writing_to_disk:
					Pref.writing_to_disk = True
					sublime.set_timeout(lambda:self.write(), 0);

	def write(self):
		if debug:
			print 'writing to disk'
		gz = GzipFile(database, 'wb')
		dump(db, gz, -1)
		gz.close()
		Pref.writing_to_disk = False

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
			return str(window.id())+str(index)
		else:
			return '0'

	def restore(self, view, where = 'unknow'):
		if view is None or not view.file_name() or view.settings().get('is_widget'):
			return

		if view.is_loading():
			sublime.set_timeout(lambda: self.restore(view, where), 100)
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
				if view.settings().get('syntax') != db[id]['x'] and lexists(sublime.packages_path()+'/../'+db[id]['x']):
					view.settings().set('syntax', db[id]['x'])

				# scroll
				if int(sublime.version()) >= 2151:
					if index in db[id]['l']:
						view.set_viewport_position(tuple(db[id]['l'][index]), False)
					else:
						view.set_viewport_position(tuple(db[id]['l']['0']), False)

	def synch(self, view = None, where = 'unknow'):
		if view is None:
			view = Pref.synch_scroll_current_view_object

		if view is None or not view.file_name() or view.settings().get('is_widget'):
			return

		# if there is something to synch
		if not Pref.synch_bookmarks and not Pref.synch_marks and not Pref.synch_folds:
			return
		Pref.synch_data_running = True


		if view.is_loading():
			Pref.synch_data_running = False
			sublime.set_timeout(lambda: self.synch(view, where), 200)
		else:

			self.save(view, 'synch')

			# if there is clones
			clones = []
			for window in sublime.windows():
				for _view in window.views():
					if _view.file_name() == view.file_name() and view.id() != _view.id():
						clones.append(_view)
			if not clones:
				Pref.synch_data_running = False
				return

			id, index = self.view_id(view)

			#print 'sync bookmarks, marks, folds'

			if Pref.synch_bookmarks:
				bookmarks = []
				for r in db[id]['b']:
					bookmarks.append(sublime.Region(int(r[0]), int(r[1])))

			if Pref.synch_marks:
				marks = []
				for r in db[id]['m']:
					marks.append(sublime.Region(int(r[0]), int(r[1])))

			if Pref.synch_folds:
				folds = []
				for r in db[id]['f']:
					folds.append(sublime.Region(int(r[0]), int(r[1])))

			for _view in clones:

				# bookmarks
				if Pref.synch_bookmarks:
					if bookmarks:
						if bookmarks != _view.get_regions('bookmarks'):
							_view.erase_regions("bookmarks")
							if debug:
								print 'synching bookmarks'
							_view.add_regions("bookmarks", bookmarks, "bookmarks", "bookmark", sublime.HIDDEN | sublime.PERSISTENT)
						else:
							if debug:
								print 'skipping synch of bookmarks these are equal'
					else:
						_view.erase_regions("bookmarks")

				# marks
				if Pref.synch_marks:
					if marks:
						if marks != _view.get_regions('mark'):
							_view.erase_regions("mark")
							if debug:
								print 'synching marks'
							_view.add_regions("mark", marks, "mark", "dot", sublime.HIDDEN | sublime.PERSISTENT)
						else:
							if debug:
								print 'skipping synch of marks these are equal'
					else:
						_view.erase_regions("mark")

				# folds
				if Pref.synch_folds:
					if int(sublime.version()) >= 2167:
						if folds:
							if folds != _view.folded_regions():
								if debug:
									print 'synching folds'
								_view.unfold(sublime.Region(0, _view.size()))
								_view.fold(folds)
							else:
								if debug:
									print 'skipping synch of folds these are equal'
						else:
							_view.unfold(sublime.Region(0, _view.size()))
					else:
						if debug:
							print 'synching folds'
						_view.unfold(sublime.Region(0, _view.size()))
						_view.fold(folds)

		Pref.synch_data_running = False

	def synch_scroll(self):

		Pref.synch_scroll_running = True

		# find current view
		view = Pref.synch_scroll_current_view_object
		if view is None or view.is_loading():
			Pref.synch_scroll_running = False
			return

		# if something changed
		if Pref.synch_scroll_last_view_id != Pref.current_view:
			Pref.synch_scroll_last_view_id = Pref.current_view
			Pref.synch_scroll_last_view_position = 0
		last_view_position = [view.visible_region(), view.viewport_position(), view.viewport_extent()]
		if Pref.synch_scroll_last_view_position == last_view_position:
			Pref.synch_scroll_running = False
			return
		Pref.synch_scroll_last_view_position = last_view_position

		# if there is clones
		clones = {}
		clones_positions = []
		for window in sublime.windows():
			for _view in window.views():
				if not _view.is_loading() and _view.file_name() == view.file_name() and view.id() != _view.id():
					id, index = self.view_id(_view)
					if index == '0':
						index  = str(window.id())+'(0, 0)'
					clones[index] = _view
					clones_positions.append(index)
		if not clones_positions:
			Pref.synch_scroll_running = False
			return

		#print 'sync scroll'

		# current view
		id, index = self.view_id(view)
		if index == '0':
			index  = str(view.window().id())+'(0, 0)'

		# append current view to list of clones
		clones[index] = view
		clones_positions.append(index)
		clones_positions.sort()

		# find current view index
		i = [i for i,x in enumerate(clones_positions) if x == index][0]

		lenght = len(clones_positions)
		line 	 = view.line_height()
		# synch scroll for views to the left
		b = i-1
		previous_view = view
		while b > -1:
			current_view = clones[clones_positions[b]]
			ppl, ppt = current_view.text_to_layout(previous_view.line(previous_view.visible_region().a).b)
			cpw, cph = current_view.viewport_extent()
			left, old_top = current_view.viewport_position()
			top = ((ppt-cph)+line)
			if abs(old_top-top) >= line:
				current_view.set_viewport_position((left, top))
			previous_view = current_view
			b -= 1

		# synch scroll for views to the right
		i += 1
		previous_view = view
		while i < lenght:
			current_view = clones[clones_positions[i]]
			top = current_view.text_to_layout(previous_view.line(previous_view.visible_region().b).a)
			left, old_top = current_view.viewport_position()
			top = top[1]-3 # 3 is the approximated height of the shadow of the tabbar. Removing the shadow Makes the text more readable
			if abs(old_top-top) >= line:
				current_view.set_viewport_position((left, top))
			previous_view = current_view
			i += 1

		Pref.synch_scroll_running = False

BufferScrollAPI = BufferScroll()

class BufferScrollForget(sublime_plugin.ApplicationCommand):
	def run(self, what):
		if what == 'color_scheme':
			sublime.active_window().active_view().settings().erase('color_scheme')

class BufferScrollReFold(sublime_plugin.WindowCommand):
	def run(self):
		view = sublime.active_window().active_view()
		if view is not None:
			id, index = BufferScrollAPI.view_id(view)
			if id in db:
				if 'pf' in db[id]:
					rs = []
					for r in db[id]['pf']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.fold(rs)

	def is_enabled(self):
		view = sublime.active_window().active_view()
		if view is not None and view.file_name():
			id, index = BufferScrollAPI.view_id(view)
			if id in db:
				if 'pf' in db[id] and len(db[id]['pf']):
					return True
		return False

def synch_scroll_loop():
	synch_scroll = BufferScrollAPI.synch_scroll
	while True:
		if Pref.synch_scroll and not Pref.synch_scroll_running:
			Pref.synch_scroll_running = True
			sublime.set_timeout(lambda:synch_scroll(), 0)
		time.sleep(0.08)
if not 'running_synch_scroll_loop' in globals():
	running_synch_scroll_loop = True
	thread.start_new_thread(synch_scroll_loop, ())

def synch_data_loop():
	synch = BufferScrollAPI.synch
	while True:
		if not Pref.synch_data_running:
			sublime.set_timeout(lambda:synch(None, 'thread'), 0)
		time.sleep(0.5)
if not 'running_synch_data_loop' in globals():
	running_synch_data_loop = True
	thread.start_new_thread(synch_data_loop, ())