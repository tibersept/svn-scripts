import sys, getopt, subprocess, re

# set
def create(config):
	return MergeRevision(config)


class MergeRevision:
	def __init__(self, config):
		self.__ARGS = sys.argv[1:]

		self.__CONST = {}

		self.__CONST['temp_path'] = config["temp_folder"] if "temp_folder" in config else 0

		self.__CONST['svn_env'] = config["svn_env"]

		self.__CONST['ignore_file_list'] = config["ignore_file_list"]

		self.__CONST['svn_location'] = config["svn_location"]

	def execute(self, arguments = None):
		if arguments == None:
			arguments = self.__ARGS
	
		svn_location = self.__CONST['svn_location']
		svn_env = self.__CONST['svn_env']
		ignore_file_list = self.__CONST['ignore_file_list']
		show_colliding_files = False
		config = {}

		try:
			options, args = getopt.getopt(arguments,'',['range=','revision=','revisions=','ignore=','show-colliding-files'])
		except getopt.GetoptError:
			self.__getOut()

		for opt, arg in options:
			if opt == '--revision':
				config['svn_revision'] = arg
			if opt == '--range':
				config['svn_range'] = arg
			if opt == '--revisions':
				config['svn_revisions'] = arg
			if opt == '--ignore':
				config['svn_ignore_revisions'] = arg
			if opt == '--show-colliding-files':
				show_colliding_files = True

		if not 'svn_range' in config:
			self.__getOut()
		if (not 'svn_revision' in config) and (not 'svn_revisions' in config):
			self.__getOut()

		# parse the target revision
		revisions = []
		is_single_revision = True
		try:
			revisions = [int(config['svn_revision'])]
		except:
			try:
				multiple_revisions = config['svn_revisions'].split(',')
				for single_revision in multiple_revisions:
					revisions.append(int(single_revision.strip()))
				is_single_revision = False
			except:
				self.__getOut()

		ignored_revisions = set()
		try:
			if 'svn_ignore_revisions' in config:
				multiple_revisions = config['svn_ignore_revisions'].split(',')
				for single_revision in multiple_revisions:
					ignored_revisions.add(int(single_revision))
		except:
			pass

		# find the commits in the specified range; sorted by their revision number
		repo_path = svn_location['repo'] + svn_env['trunk']
		cmd_args = ['svn','log','-v','-r' + config['svn_range']]
		cmd_args.append(repo_path)
		cmd_str = ' '.join(cmd_args)
		cmd = subprocess.Popen(cmd_args, stdout=subprocess.PIPE)
		cmd_out, cmd_err = cmd.communicate()

		commits = [];
		if len(cmd_out) > 0:
			commits = self.__parseLog(cmd_out, config)
		else:
			print('No revisions to merge')
			return

		checked_revisions = []
		for revision in revisions:
			if revision in [c['revision'] for c in commits]:
				checked_revisions.append(revision)

		if len(checked_revisions)<=0:
			if is_single_revision:
				print('The provided revision number ['+str(revisions[0])+'] is not in the merge list')
			else:
				print('None of the provided revision numbers is in the merge list')
			return

		# also ignore the revisions that are being checked, their mutual dependency is irrelevant
		for revision in checked_revisions:
			ignored_revisions.add(revision)

		# find the merge information; sorted by revision
		cmd_args = ['svn','propget','svn:mergeinfo']
		cmd_args.append(svn_location['local'])
		cmd_str = ' '.join(cmd_args)
		cmd = subprocess.Popen(cmd_args, stdout=subprocess.PIPE)
		cmd_out, cmd_err = cmd.communicate()

		merges = {}
		if len(cmd_out) > 0:
			merges = self.__parseMergeInfo(cmd_out, config)
		else:
			print('No merge info, everything can be merged')
			return

		# get the ranges for the source merge path we are interested in
		try:
			ranges = merges[svn_env['trunk']]
		except:
			print('No merges from '+svn_env['trunk']+' present!')
			return

		# find the start position in the merge info 
		position = 0;
		if (len(commits)>0 and len(ranges)>0):
			first_commit = commits[0]
			position = self.__findRangePosition(ranges, first_commit)

		# eliminate the commits that are already merged
		# if the first commit was not in the range then none of them are
		# else find commits that are already merged and filter them out
		if position>=0:
			commits = [c for c in commits if not self.__isMerged(ranges, c, position)]

		print('---------------------------------------------------------------')	
		print('There are ['+str(len(commits))+'] commits to be merged.')
		print('')	

		# prepare the ignore list for files to be ignored for collisions
		ignored_files = {}
		for file_path in ignore_file_list:
			full_path = svn_env['trunk'] + file_path
			ignored_files[full_path] = True

		collisions = {}
		collisions['items'] = []
		collisions['opnumbers'] = set()
		collisions['contains'] = set()

		for revision in checked_revisions:
			self.__findCollisions(commits, revision, collisions, ignored_files, ignored_revisions)

		all_collisions = collisions['items']

		# group by task number		
		collisions_by_op_number = {}
		for co in all_collisions:
			op_number = co['opnumber']
			if not (op_number in collisions_by_op_number):
				collisions_by_op_number[op_number] = []
			collisions_by_op_number[op_number].append(co);

		# sort by revision in each group
		for op_number in collisions_by_op_number:
			collisions_by_op_number[op_number] = sorted(
				collisions_by_op_number[op_number], 
				key=lambda co: co['revision']
			)

		# print out report
		if collisions_by_op_number:
			if is_single_revision:
				print('Revision ['+str(revisions[0])+'] collides with the following commits:')
			else:
				print(
					'Provided revisions ['
					+ self.__revisions_as_string(checked_revisions, ', ')
					+'] collide with the following commits:'
				)
			for op_number in collisions_by_op_number:
				task_collisions = collisions_by_op_number[op_number]
				print(' * Task ['+op_number+'] collisions:')
				for co in task_collisions:
					print('   * ', end='')
					print(
						'Revision: ['
						+ str(co['revision'])
						+ ']'
					)
				print('')
			print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
			if is_single_revision:
				print('One liner: '+str(revisions[0])+' - ', end='')
			else:
				print('One liner: '+ self.__revisions_as_string(checked_revisions, '/')+' - ', end='')
			first_op_number = True
			for op_number in collisions_by_op_number:
				if not first_op_number:
					print(', ', end='')
				first_op_number = False
				task_collisions = collisions_by_op_number[op_number]
				first_task_collision = True
				for co in task_collisions:
					if not first_task_collision:
						print('/', end='')
					first_task_collision = False
					print(str(co['revision']), end='')
				print('('+op_number+')',end='')
			print('')
			print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

			if show_colliding_files:
				print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
				print('Detailed report listing colliding files follows:')
				print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
				for co in all_collisions:
					print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
					if not co['filecollision']:
						print('Revision ['
								+ str(co['revision'])
								+ '] has no colliding files but references Task ['
								+ co['opnumber']
								+ ']'
						)
					else:
						file_collision_reason = ' directly with revision ['+str(co['collideswith'])+']'
						if co['depth']!=0:
							file_collision_reason = ' indirectly via revision ['+str(co['collideswith'])+']'
						print(
							'Revision: ['
							+ str(co['revision'])
							+ '] for task: ['
							+ co['opnumber']
							+ '] collides'
							+ file_collision_reason
						)
						print('Files:')
						for file_path in co['files']:
							print('>> ' + file_path)

					print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
					print('')
		else:
			print('No collisions detected, merge can be performed')

		print('---------------------------------------------------------------')	
		print('Done.')

	def __revisions_as_string(self, revisions, separator):
		return separator.join(map(lambda x: str(x), revisions))
	
	def __findCollisions(self, commits, revision, collisions, ignored_files, ignored_revisions, depth = 0):
		# get the target commit
		position = self.__findCommitPosition(commits, revision)
		if position < 0:
			return
		if position == 0:
			return

		# prepare the target commit, it's files become a set
		target_commit = commits[position]
		target_commit_files = {}
		for file_path in target_commit['files']:
			target_commit_files[file_path] = True

		# truncate the commits to preceding ones only
		position_commits = commits[:position]

		collision_closure = [];

		# find the collisions
		for c in position_commits:
			colliding_revision = c['revision']
			if colliding_revision in ignored_revisions:
				continue
			op_number = c['opnumber']

			files = []
			for file_path in c['files']:
				if file_path in ignored_files:
					continue
				if file_path in target_commit_files:
					files.append(file_path)

			file_collision_found = (len(files)>0)
			task_collision_found = (op_number in collisions['opnumbers'])
			collision_present = (colliding_revision in collisions['contains'])

			if (file_collision_found or task_collision_found) and (not collision_present):
				collisions['contains'].add(colliding_revision)
				collisions['opnumbers'].add(op_number)
				collision_closure.append(colliding_revision)

				collision = {}
				collision['revision'] = colliding_revision
				collision['opnumber'] = op_number
				collision['files'] = files
				collision['depth'] = depth
				collision['filecollision'] = file_collision_found 

				if (file_collision_found):
					collision['collideswith'] = target_commit['revision']
				else:
					collision['collideswith'] = None

				collisions['items'].append(collision)
		
		# recursive closure determination
		for colloding_revision in collision_closure:
			self.__findCollisions(commits, colliding_revision, collisions, ignored_files, ignored_revisions, depth+1)

	def __parseLog(self, svn_str, config):
		commits = []

		svn_log_output = re.sub(r'(\-{10,})([\n\r]+)', "BREAK\n\n", svn_str.decode('utf-8'))
		svn_log_lines = svn_log_output.split("BREAK\n\n")

		if len(svn_log_lines) <= 0:
			return commits;

		for svn_log_line in svn_log_lines:
			tmp = svn_log_line.strip()
			if (len(tmp) > 0):
				commits.append(tmp)
		
		if len(commits) > 0:
			for i,svn_log_line in enumerate(commits):
				tmp_log_data =  self.__parseLogData(svn_log_line)
				if tmp_log_data:
					commits[i] = tmp_log_data

		return commits

	def __parseLogData(self, log_data):
		obj = {}

		log_data_lines = log_data.split('\n')

		if len(log_data_lines) <= 0:
			return obj

		tmp = log_data_lines[0].strip().split("|")

		for i,val in enumerate(tmp):
			val = val.strip()
			if (i == 0):
				obj['revision'] = int(val[1:])
			if (i == 1):
				obj['user'] = val
			if (i == 2):
				obj['timestamp'] = val
				if (i == 3):
					obj['lines'] = val

		obj['files'] = []
		
		if len(log_data_lines) < 2:
			return obj

		svn_env = self.__CONST['svn_env']
		location = svn_env['trunk']

		rest = log_data_lines[1:]
		comment_pending = False 
		comment_set = False

		for line in rest:
			line_entry = line.strip();

			if (len(line_entry)==0):
				comment_pending = True
			elif comment_pending:
				if not comment_set: 
					obj['comment'] = line_entry
				else:
					obj['comment'] = obj['comment'] + '\n' + line_entry
			
				if not comment_set:
					line_search = re.search('\[.*\]\s*\(\s*(OP\s*\d+)\){1}', line_entry, re.IGNORECASE)
					if line_search:
						op_number = line_search.group(1)
						op_number = re.sub('\s*OP\s*', "#", op_number)
						obj['opnumber'] = op_number
						break
					else:
						line_search = re.search('\[.*\]\s*\(\s*(\w+)\){1}', line_entry, re.IGNORECASE)
						if line_search:
							op_number = line_search.group(1)
							obj['opnumber'] = op_number
						else:
							obj['opnumber'] = 'unknown'
				comment_set = True
			else:
				if line_entry.startswith(('A ', 'D ', 'U ', 'M ', 'G ', 'E ', 'R ')):
					file_path = line_entry[2:].strip()
					obj['files'].append(file_path)

		return obj

	def __parseMergeInfo(self, merge_info, config):
		merges = {};

		merge_info_lines = merge_info.decode('utf-8').split('\n')

		if len(merge_info_lines)<=0:
			return merges;
		
		for info_line in merge_info_lines:
			merge_item = [];
			info_item = info_line.split(':')
			if len(info_item)<2:
				continue

			merge_source_path = info_item[0].strip()
			if merge_source_path in merges:
				merge_item = merges[merge_source_path]
			else:
				merges[merge_source_path] = merge_item
			
			merge_revisions_combined = info_item[1]
			if len(merge_revisions_combined)<=0:
				continue

			merge_revisions = merge_revisions_combined.split(',')
			if len(merge_revisions)<=0:
				continue

			for revision in merge_revisions:
				revision_item = {}
				revision_range = revision.split('-')
				if len(revision_range)>1:
					revision_item['from'] = int(revision_range[0].strip())
					revision_item['to'] = int(revision_range[1].strip())
				elif len(revision_range)==1:
					revision_item['from'] = int(revision_range[0].strip())
					revision_item['to'] = int(revision_range[0].strip())
				else:
					continue
				merge_item.append(revision_item)

		return merges

	def __findRangePosition(self, ranges, commit):
		if len(ranges) <= 0:
			return -1

		position = 0
		rev = commit['revision']
		for r in ranges:
			if (rev>=r['from'] and rev<=r['to']):
				return position
			if rev<r['from']:
				return position
			position = position + 1
		return -1

	def __findCommitPosition(self, commits, revision):
		if len(commits) <= 0:
			return -1

		position = 0
		for c in commits:
			if c['revision'] == revision:
				return position
			position = position + 1
		return -1

	def __isMerged(self, ranges, commit, start):
		if len(ranges) <= 0:
			return False
		target_ranges = ranges
		if start > 0:
			target_ranges = ranges[start:]

		rev = commit['revision']
		for r in target_ranges:
			if (rev>=r['from'] and rev<=r['to']):
				return True
		return False
	
	#	merge_prompt = self.__sysPrompt('Do You want to execute the svn merge?')
	#if merge_prompt:
	def __sysPrompt(self, prompt_str):
		sys.stdout.write(prompt_str + ' [y/n]: ')
		choice = raw_input().lower()
		
		if choice == 'y' or choice == 'yes':
			ret = 1
		else:
			ret = 0
		return ret	
	
	def __getOut(self):
		print('usage: merge.py [--revision=<revision>|--revisions=<revision>,<revision>...] --range=<revision>:<revision> [--ignore=<revision>,<revision>] [--show-colliding-files]')
		sys.exit(2)
