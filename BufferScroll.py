import sublime
import sublime_plugin
import os
import hashlib

settings = sublime.load_settings('BufferScroll.sublime-settings')

version = 2
version_current = settings.get('version', 0)
if version_current < version:
	settings.set('version', version)
	settings.set('buffers', {})
	settings.set('queue', [])
	sublime.save_settings('BufferScroll.sublime-settings')
	settings = sublime.load_settings('BufferScroll.sublime-settings')

buffers = settings.get('buffers', {})
queue = settings.get('queue', [])

class BufferScroll(sublime_plugin.EventListener):

	def on_load(self, view):
		if view.file_name() != None and view.file_name() != '':
			# restore on preview tabs should be fast as posible
			self.restore(view)
			# overwrite restoration of scroll made by the application
			sublime.set_timeout(lambda: self.restoreScroll(view), 200)

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
		hash = hashlib.sha1(os.path.normpath(view.file_name().encode('utf-8'))).hexdigest()[:7]
		hash += ':'+str(view.window().get_view_index(view) if view.window() else '')

		buffer = {}
		# if the size of the view change outside the application skip restoration
		buffer['id'] = long(view.size())
		# scroll
		buffer['l'] = list(view.viewport_position())

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
		folds = view.unfold(sublime.Region(0, view.size()))
		for r in folds:
			line_s, col_s = view.rowcol(r.a); line_e, col_e = view.rowcol(r.b)
			buffer['f'].append([view.text_point(line_s, col_s), view.text_point(line_e, col_e)])
		view.fold(folds)

		buffers[hash] = buffer

		if hash in queue:
			queue.remove(hash)
		queue.append(hash)
		if len(queue) > 2000:
			hash = queue.pop(0)
			del buffers[hash]
		settings.set('buffers', buffers)
		settings.set('queue', queue)
		sublime.save_settings('BufferScroll.sublime-settings')

	def restore(self, view):
		hash = hashlib.sha1(os.path.normpath(view.file_name().encode('utf-8'))).hexdigest()[:7]
		hash += ':'+str(view.window().get_view_index(view) if view.window() else '')
		if hash in buffers:
			buffer = buffers[hash]
			if long(buffer['id']) == long(view.size()):
				view.sel().clear()
				# fold
				for r in buffer['f']:
					view.fold(sublime.Region(int(r[0]), int(r[1])))
				# selection
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
				if buffer['l']:
					view.set_viewport_position(tuple(buffer['l']), False)

	def restoreScroll(self, view):
		hash = hashlib.sha1(os.path.normpath(view.file_name().encode('utf-8'))).hexdigest()[:7]
		hash += ':'+str(view.window().get_view_index(view) if view.window() else '')
		if hash in buffers:
			buffer = buffers[hash]
			if long(buffer['id']) == long(view.size()):
				if buffer['l']:
					view.set_viewport_position(tuple(buffer['l']), False)