import sublime, sublime_plugin
from os.path import lexists, normpath, dirname
from os import makedirs
from hashlib import sha1
from gzip import GzipFile
import _thread as thread
from pickle import load, dump
import time
from os.path import basename

# import inspect

def plugin_loaded():
	global debug, database, Pref, BufferScrollAPI, db, s
	debug = False

	# open
	db = {}
	database = dirname(sublime.packages_path())+'/Settings/BufferScroll.bin.gz'
	try:
		makedirs(dirname(database))
	except:
		pass
	try:
		gz = GzipFile(database, 'rb')
		db = load(gz);
		gz.close()
	except:
		db = {}

	# settings
	s = sublime.load_settings('BufferScroll.sublime-settings')
	Pref = Pref()
	Pref.load()
	s.add_on_change('reload', 	lambda:Pref.load())

	BufferScrollAPI = BufferScroll()

	BufferScrollAPI.init_()

	# threads listening scroll, and waiting to set data on focus change
	if not 'running_synch_data_loop' in globals():
		global running_synch_data_loop
		running_synch_data_loop = True
		thread.start_new_thread(synch_data_loop, ())

	if not 'running_synch_scroll_loop' in globals():
		global running_synch_scroll_loop
		running_synch_scroll_loop = True
		thread.start_new_thread(synch_scroll_loop, ())


class Pref():
	def load(self):
		Pref.remember_color_scheme 	              = s.get('remember_color_scheme', False)
		Pref.synch_bookmarks 				              = s.get('synch_bookmarks', False)
		Pref.synch_marks 						              = s.get('synch_marks', False)
		Pref.synch_folds 						              = s.get('synch_folds', False)
		Pref.synch_scroll 					              = s.get('synch_scroll', False)
		Pref.typewriter_scrolling									= s.get('typewriter_scrolling', False)
		Pref.use_animations												= s.get('use_animations', False)
		Pref.i_use_cloned_views										= s.get('i_use_cloned_views', False)

		Pref.current_view_id				              = -1
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

	# syntax specific settings
	def get(self, type, view):

		if view.settings().has('bs_sintax'):
			syntax = view.settings().get('bs_sintax')
		else:
			syntax = view.settings().get('syntax')
			syntax = basename(syntax).replace('.tmLanguage', '').lower() if syntax != None else "plain text"
			view.settings().set('bs_sintax', syntax);

		if hasattr(Pref, syntax) and type in getattr(Pref, syntax):
			return getattr(Pref, syntax)[type];
		elif hasattr(Pref, syntax) and type not in getattr(Pref, syntax):
			return getattr(Pref, type)
		elif s.has(syntax):
			setattr(Pref, syntax, s.get(syntax))
			self.get(type, view);
		else:
			return getattr(Pref, type)

class BufferScroll(sublime_plugin.EventListener):

	def init_(self):
		self.on_load(sublime.active_window().active_view())
		for window in  sublime.windows():
			self.on_load(window.active_view())

	# restore on load for new opened tabs or previews.
	def on_load(self, view):
		self.restore(view, 'on_load')

	# restore on load for cloned views
	def on_clone(self, view):
		self.restore(view, 'on_clone')

	# save data on focus lost
	def on_deactivated(self, view):
		window = view.window();
		if not window:
			window = sublime.active_window()
		index = window.get_view_index(view)
		if index != (-1, -1): # if the view was not closed
			self.save(view, 'on_deactivated')
			self.synch_data(view)

	# track the current_view. See next event listener
	def on_activated(self, view):
		if not view.settings().get('is_widget'):
			Pref.current_view_id = view.id()
			Pref.synch_scroll_current_view_object = view

	# save data on close
	def on_pre_close(self, view):
		self.save(view, 'on_pre_close')

	# save data for focused tab when saving
	def on_pre_save(self, view):
		self.save(view, 'on_pre_save')

	# typewriter scrolling
	def on_modified(self, view):
		if Pref.get('typewriter_scrolling', view) and len(view.sel()) == 1 and not view.settings().get('is_widget') and not view.is_scratch():
			# TODO STBUG if the view is in a column, for some reason the parameter view, is not correct. This fix it:s
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
				print ('-----------------------------------')
				print ('SAVING from: '+where)
				print ('file: '+view.file_name())
				print ('id: '+id)
				print ('position: '+index)


			# creates an object for this view, if it is unknow to the package
			if id not in db:
				db[id] = {}

			# if the result of the new collected data is different
			# from the old data, then will write to disk
			# this will hold the old value for comparation
			old_db = dict(db[id])

			# if the size of the view change outside the application skip restoration
			# if not we will restore folds in funny positions, etc...
			db[id]['id'] = int(view.size())

			# scroll
			if 'l' not in db[id]:
				db[id]['l'] = {}
			# save the scroll with "index" as the id ( for cloned views )
			db[id]['l'][index] = view.viewport_position()
			# also save as default if no exists
			db[id]['l']['0'] = view.viewport_position()
			if debug:
				print('viewport_position: '+str(view.viewport_position()))

			# selections
			db[id]['s'] = [[item.a, item.b] for item in view.sel()]
			if debug:
				print('selections: '+str(db[id]['s']))

			# marks
			db[id]['m'] = [[item.a, item.b] for item in view.get_regions("mark")]
			if debug:
				print('marks: '+str(db[id]['m']))

			# bookmarks
			db[id]['b'] = [[item.a, item.b] for item in view.get_regions("bookmarks")]
			if debug:
				print('bookmarks: '+str(db[id]['b']))

			# previous folding save, to be able to refold
			if 'f' in db[id] and list(db[id]['f']) != []:
				db[id]['pf'] = list(db[id]['f'])

			# folding
			db[id]['f'] = [[item.a, item.b] for item in view.folded_regions()]
			if debug:
				print('fold: '+str(db[id]['f']))

			# color_scheme http://www.sublimetext.com/forum/viewtopic.php?p=25624#p25624
			if Pref.get('remember_color_scheme', view):
				db[id]['c'] = view.settings().get('color_scheme')
				if debug:
					print('color_scheme: '+str(db[id]['c']))

			# syntax
			db[id]['x'] = view.settings().get('syntax')
			if debug:
				print('syntax: '+str(db[id]['x']))

			# write to disk only if something changed
			if old_db != db[id] or where == 'on_deactivated':
				if not Pref.writing_to_disk:
					Pref.writing_to_disk = True
					sublime.set_timeout(lambda:self.write(), 0);

	def write(self):
		if debug:
			print ('writing to disk')
		gz = GzipFile(database, 'wb')
		dump(db, gz, -1)
		gz.close()
		Pref.writing_to_disk = False

	def view_id(self, view):
		if not view.settings().has('buffer_scroll_name'):
			view.settings().set('buffer_scroll_name', sha1(normpath(str(view.file_name()).encode('utf-8'))).hexdigest()[:8])
		return (view.settings().get('buffer_scroll_name'), self.view_index(view))

	def view_index(self, view):
		window = view.window();
		if not window:
			window = sublime.active_window()
		index = window.get_view_index(view)
		return str(window.id())+str(index)

	def restore(self, view, where = 'unknow'):
		if view is None or not view.file_name() or view.settings().get('is_widget'):
			return

		if view.is_loading():
			sublime.set_timeout(lambda: self.restore(view, where), 100)
		else:

			id, index = self.view_id(view)

			if debug:
				print ('-----------------------------------')
				print ('RESTORING from: '+where)
				print ('file: '+view.file_name())
				print ('id: '+id)
				print ('position: '+index)

			if id in db:

				# if the view changed outside of the application, don't restore folds etc
				if db[id]['id'] == int(view.size()):

					# fold
					rs = []
					for r in db[id]['f']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.fold(rs)
						if debug:
							print("fold: "+str(rs));

					# selection
					if len(db[id]['s']) > 0:
						view.sel().clear()
						for r in db[id]['s']:
							view.sel().add(sublime.Region(int(r[0]), int(r[1])))
						if debug:
							print('selection: '+str(db[id]['s']));

					# marks
					rs = []
					for r in db[id]['m']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.add_regions("mark", rs, "mark", "dot", sublime.HIDDEN | sublime.PERSISTENT)
						if debug:
							print('marks: '+str(db[id]['m']));

					# bookmarks
					rs = []
					for r in db[id]['b']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.add_regions("bookmarks", rs, "bookmarks", "bookmark", sublime.HIDDEN | sublime.PERSISTENT)
						if debug:
							print('bookmarks: '+str(db[id]['b']));

				# color scheme
				if Pref.get('remember_color_scheme', view) and 'c' in db[id] and view.settings().get('color_scheme') != db[id]['c']:
					view.settings().set('color_scheme', db[id]['c'])
					if debug:
						print('color scheme: '+str(db[id]['c']));

				# syntax
				if view.settings().get('syntax') != db[id]['x'] and lexists(sublime.packages_path()+'/../'+db[id]['x']):
					view.settings().set('syntax', db[id]['x'])
					if debug:
						print('syntax: '+str(db[id]['x']));

				# scroll
				if Pref.get('i_use_cloned_views', view) and index in db[id]['l']:
					position = tuple(db[id]['l'][index])
					view.set_viewport_position(position, Pref.get('use_animations', view))
				else:
					position = tuple(db[id]['l']['0'])
					view.set_viewport_position(position, Pref.get('use_animations', view))
				sublime.set_timeout(lambda: self.stupid_scroll(view, position), 0)
				if debug:
					print('scroll set: '+str(position));
					print('supposed current scroll: '+str(view.viewport_position())); # THIS LIES

	def stupid_scroll(self, view, position):
		if not view.visible_region().contains(view.sel()[0]):
			view.set_viewport_position(position, Pref.get('use_animations', view))

	def synch_data(self, view = None, where = 'unknow'):
		if view is None:
			view = Pref.synch_scroll_current_view_object

		if view is None or view.settings().get('is_widget'):
			return

		# if there is something to synch
		if not Pref.get('synch_bookmarks', view) and not Pref.get('synch_marks', view) and not Pref.get('synch_folds', view):
			return
		Pref.synch_data_running = True


		if view.is_loading():
			Pref.synch_data_running = False
			sublime.set_timeout(lambda: self.synch_data(view, where), 200)
		else:

			self.save(view, 'synch')

			# if there is clones
			clones = []
			for window in sublime.windows():
				for _view in window.views():
					if _view.buffer_id() == view.buffer_id() and view.id() != _view.id():
						clones.append(_view)
			if not clones:
				Pref.synch_data_running = False
				return

			id, index = self.view_id(view)

			#print 'sync bookmarks, marks, folds'

			if Pref.get('synch_bookmarks', view):
				bookmarks = []
				for r in db[id]['b']:
					bookmarks.append(sublime.Region(int(r[0]), int(r[1])))

			if Pref.get('synch_marks', view):
				marks = []
				for r in db[id]['m']:
					marks.append(sublime.Region(int(r[0]), int(r[1])))

			if Pref.get('synch_folds', view):
				folds = []
				for r in db[id]['f']:
					folds.append(sublime.Region(int(r[0]), int(r[1])))

			for _view in clones:

				# bookmarks
				if Pref.get('synch_bookmarks', _view):
					if bookmarks:
						if bookmarks != _view.get_regions('bookmarks'):
							_view.erase_regions("bookmarks")
							if debug:
								print ('synching bookmarks')
							_view.add_regions("bookmarks", bookmarks, "bookmarks", "bookmark", sublime.HIDDEN | sublime.PERSISTENT)
						else:
							if debug:
								print ('skipping synch of bookmarks these are equal')
					else:
						_view.erase_regions("bookmarks")

				# marks
				if Pref.get('synch_marks', _view):
					if marks:
						if marks != _view.get_regions('mark'):
							_view.erase_regions("mark")
							if debug:
								print ('synching marks')
							_view.add_regions("mark", marks, "mark", "dot", sublime.HIDDEN | sublime.PERSISTENT)
						else:
							if debug:
								print ('skipping synch of marks these are equal')
					else:
						_view.erase_regions("mark")

				# folds
				if Pref.get('synch_folds', _view):
					if folds:
						if folds != _view.folded_regions():
							if debug:
								print ('synching folds')
							_view.unfold(sublime.Region(0, _view.size()))
							_view.fold(folds)
						else:
							if debug:
								print ('skipping synch of folds these are equal')
					else:
						_view.unfold(sublime.Region(0, _view.size()))

		Pref.synch_data_running = False

	def synch_scroll(self):

		Pref.synch_scroll_running = True

		# find current view
		view = Pref.synch_scroll_current_view_object
		if view is None or view.is_loading() or not Pref.get('synch_scroll', view):
			Pref.synch_scroll_running = False
			return

		# if something changed
		if Pref.synch_scroll_last_view_id != Pref.current_view_id:
			Pref.synch_scroll_last_view_id = Pref.current_view_id
			Pref.synch_scroll_last_view_position = 0
		last_view_position = str([view.visible_region(), view.viewport_position(), view.viewport_extent()])
		if Pref.synch_scroll_last_view_position == last_view_position:
			Pref.synch_scroll_running = False
			return
		Pref.synch_scroll_last_view_position = last_view_position

		# if there is clones
		clones = {}
		clones_positions = []
		for window in sublime.windows():
			for _view in window.views():
				if not _view.is_loading() and _view.buffer_id() == view.buffer_id() and view.id() != _view.id():
					id, index = self.view_id(_view)
					clones[index] = _view
					clones_positions.append(index)
		if not clones_positions:
			Pref.synch_scroll_running = False
			return

		# current view
		id, index = self.view_id(view)

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
		if not Pref.synch_scroll_running:
			Pref.synch_scroll_running = True
			sublime.set_timeout(lambda:synch_scroll(), 0)
		time.sleep(0.08)

def synch_data_loop():
	synch_data = BufferScrollAPI.synch_data
	while True:
		if not Pref.synch_data_running:
			sublime.set_timeout(lambda:synch_data(None, 'thread'), 0)
		time.sleep(0.5)
