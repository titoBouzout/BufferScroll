import sublime
import sublime_plugin
import os
import hashlib

settings = sublime.load_settings('BufferScroll.sublime-settings')

version = 5
version_current = settings.get('version', version)
if version_current < version:
	settings.set('version', version)
	settings.set('buffers', {})
	settings.set('queue', [])
	sublime.save_settings('BufferScroll.sublime-settings')
	settings = sublime.load_settings('BufferScroll.sublime-settings')

buffers = settings.get('buffers', {})
queue = settings.get('queue', [])

class BufferScroll(sublime_plugin.EventListener):

	# restore on load for new opened tabs or previews.
	def on_load(self, view):
		if view.file_name() != None and view.file_name() != '' and not view.settings().get('is_widget'):
			# restore on preview tabs should be fast as posible
			self.restore(view)
			# overwrite restoration of scroll made by the application
			sublime.set_timeout(lambda: self.restore_scroll(view), 200)

	# restore on load for cloned views
	def on_clone(self, view):
		if view.file_name() != None and view.file_name() != '' and not view.settings().get('is_widget'):
			# restore on preview tabs should be fast as posible
			self.restore(view)
			# overwrite restoration of scroll made by the application
			sublime.set_timeout(lambda: self.restore_scroll(view), 200)

	# the application is not sending "on_close" event when closing
	# or switching the projects, then we need to save the data on focus lost
	def on_deactivated(self, view):
		if view.file_name() != None and view.file_name() != '':
			self.save(view)

	# save the data when background tabs are closed
	# these that don't receive "on_deactivated"
	def on_close(self, view):
		if view.file_name() != None and view.file_name() != '':
			self.save(view)

	# save data for focused tab when saving
	def on_pre_save(self, view):
		if view.file_name() != None and view.file_name() != '':
			self.save(view)

	def save(self, view):
		buffer = {}

		# scroll
		if int(sublime.version()) >= 2151:
			buffer['l'] = list(view.viewport_position())

		# if the size of the view change outside the application skip restoration
		# if not we will restore folds in funny positions, etc...
		buffer['id'] = long(view.size())

		# selections
		buffer['s'] = []
		for r in view.sel():
			line_s, col_s = view.rowcol(r.a); line_e, col_e = view.rowcol(r.b)
			buffer['s'].append([view.text_point(line_s, col_s), view.text_point(line_e, col_e)])

		# marks
		buffer['m'] = []
		for r in view.get_regions("mark"):
			line_s, col_s = view.rowcol(r.a); line_e, col_e = view.rowcol(r.b)
			buffer['m'].append([view.text_point(line_s, col_s), view.text_point(line_e, col_e)])

		# bookmarks
		buffer['b'] = []
		for r in view.get_regions("bookmarks"):
			line_s, col_s = view.rowcol(r.a); line_e, col_e = view.rowcol(r.b)
			buffer['b'].append([view.text_point(line_s, col_s), view.text_point(line_e, col_e)])

		# folding
		buffer['f'] = []
		if int(sublime.version()) >= 2167:
			for r in view.folded_regions():
				line_s, col_s = view.rowcol(r.a); line_e, col_e = view.rowcol(r.b)
				buffer['f'].append([view.text_point(line_s, col_s), view.text_point(line_e, col_e)])
		else:
			folds = view.unfold(sublime.Region(0, view.size()))
			for r in folds:
				line_s, col_s = view.rowcol(r.a); line_e, col_e = view.rowcol(r.b)
				buffer['f'].append([view.text_point(line_s, col_s), view.text_point(line_e, col_e)])
			view.fold(folds)

		hash_filename = hashlib.sha1(os.path.normpath(view.file_name().encode('utf-8'))).hexdigest()[:7]
		hash_position = hash_filename+self.view_index(view)

		buffers[hash_filename] = buffer
		buffers[hash_position] = buffer

		if hash_position in queue:
			queue.remove(hash_position)
		if hash_filename in queue:
			queue.remove(hash_filename)
		queue.append(hash_position)
		queue.append(hash_filename)
		if len(queue) > 2000:
			hash = queue.pop(0)
			del buffers[hash]
			hash = queue.pop(0)
			del buffers[hash]
		settings.set('buffers', buffers)
		settings.set('queue', queue)
		sublime.save_settings('BufferScroll.sublime-settings')

	def restore(self, view):
		if view.is_loading():
			sublime.set_timeout(lambda: self.restore(view), 100)
		elif view.file_name():

			hash_filename = hashlib.sha1(os.path.normpath(view.file_name().encode('utf-8'))).hexdigest()[:7]
			hash_position = hash_filename+self.view_index(view)

			if hash_position in buffers:
				hash = hash_position
			else:
				hash = hash_filename

			if hash in buffers:
				buffer = buffers[hash]

				if long(buffer['id']) == long(view.size()):

					# fold
					rs = []
					for r in buffer['f']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.fold(rs)

					# selection
					if len(buffer['s']) > 0:
						view.sel().clear()
					for r in buffer['s']:
						view.sel().add(sublime.Region(int(r[0]), int(r[1])))

					# marks
					rs = []
					for r in buffer['m']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.add_regions("mark", rs, "mark", "dot", sublime.HIDDEN | sublime.PERSISTENT)

					# bookmarks
					rs = []
					for r in buffer['b']:
						rs.append(sublime.Region(int(r[0]), int(r[1])))
					if len(rs):
						view.add_regions("bookmarks", rs, "bookmarks", "bookmark", sublime.HIDDEN | sublime.PERSISTENT)

				# scroll
				if int(sublime.version()) >= 2151 and buffer['l']:
					view.set_viewport_position(tuple(buffer['l']), False)

	def restore_scroll(self, view):
		if view.is_loading():
			sublime.set_timeout(lambda: self.restore_scroll(view), 100)
		elif view.file_name():

			hash_filename = hashlib.sha1(os.path.normpath(view.file_name().encode('utf-8'))).hexdigest()[:7]
			hash_position = hash_filename+self.view_index(view)

			if hash_position in buffers:
				hash = hash_position
			else:
				hash = hash_filename
			# print  view.viewport_position();
			if hash in buffers:
				buffer = buffers[hash]
				if int(sublime.version()) >= 2151 and buffer['l']:
					view.set_viewport_position(tuple(buffer['l']), False)

	def view_index(self, view):
		if not view.window():
			return ''
		window = view.window();
		index = window.get_view_index(view)
		if index != None and index != (0,0) and index != (0,-1) and index != (-1,-1):
			return str(index)
		else:
			return '';

	def _view_index(self, view):
		return str(view.window().get_view_index(view) if view.window() else '')