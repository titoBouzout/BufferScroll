import sublime
import sublime_plugin
import os
import hashlib

settings = sublime.load_settings('BufferScroll.sublime-settings')
buffers = settings.get('buffers', {})
queue = settings.get('queue', [])

class BufferScroll(sublime_plugin.EventListener):

	def on_load(self, view):
		if view.file_name() != None and view.file_name() != '':
			self.restore(view)

	def on_deactivated(self, view):
		if view.file_name() != None and view.file_name() != '':
			self.save(view)

	def save(self, view):
		hash = hashlib.sha1(os.path.normpath(view.file_name())).hexdigest()[:7]
		buffer = {}
		buffer['id'] = view.size()
		buffer['l'] = [int(view.rowcol(view.visible_region().begin())[0]), int(view.rowcol(view.visible_region().begin())[1])]
		buffer['s'] = []
		for s in view.sel():
			line_s, col_s = view.rowcol(s.a); line_e, col_e = view.rowcol(s.b)
			buffer['s'].append([int(view.text_point(line_s, col_s)), int(view.text_point(line_e, col_e))])
		buffer['f'] = []
		folds = view.unfold(sublime.Region(0, view.size()))
		for f in folds:
			line_s, col_s = view.rowcol(f.a); line_e, col_e = view.rowcol(f.b)
			buffer['f'].append([int(view.text_point(line_s, col_s)), int(view.text_point(line_e, col_e))])
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
		hash = hashlib.sha1(os.path.normpath(view.file_name())).hexdigest()[:7]
		if hash in buffers:
			buffer = buffers[hash]
			if buffer['id'] == view.size():
				for f in buffer['f']:
					view.fold(sublime.Region(f[0], f[1]))
				view.sel().clear()
				for s in buffer['s']:
					view.sel().add(sublime.Region(s[0], s[1]))
				view.show(view.text_point(buffer['l'][0], buffer['l'][1]), False)