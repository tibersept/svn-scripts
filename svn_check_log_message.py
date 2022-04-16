from subprocess import Popen
from subprocess import PIPE
from optparse import OptionParser
import sys
import re
import os
	
def decode_output(input, codecs=["utf-8", "windows-1252", "iso8859_15", "latin_1", "ascii"]):
	for codec in codecs:
		try:
			return input.decode(codec)
		except:
			pass
		
	# set to empty, the check will fail with empty message error
	sys.stderr.write("[WARN] Your commit message cannot be decoded\n")
	sys.stderr.write("[WARN] Verify the encoding of your subversion installation\n")
	sys.stderr.write("[WARN] Supported encodings are UTF-8, WINDOWS-1252, ")
	sys.stderr.write("ISO-8859-15, ISO-8859-1 and ASCII\n")
	return ""

def command_output(cmd):
    return Popen(cmd.split(), stdout=PIPE).communicate()[0]

def get_log_message(look_cmd):
	return decode_output(command_output(look_cmd % ("log")))

def get_log_reference(log_message):
	reference_search = re.search('^\[(.*)\]',log_message, re.IGNORECASE)
	if reference_search:
		reference = reference_search.group(1)		
		return reference
	return ""

def get_project_reference(log_message):
	reference_search = re.search('^\[.*\]\(([\w|\s]*)\)', log_message, re.IGNORECASE)
	if reference_search:
		reference = reference_search.group(1)
		return reference
	return ""

def get_changed_files(look_cmd):
	def filename(line):
		return line[4:-1]
	output = decode_output(command_output(look_cmd % ("changed")))
	file_list = output.split("\n")
	changed_files = [filename(line) for line in file_list if len(line)>0]
	return changed_files
	
def remove_extension(filename_with_extension):
		filename, extension = os.path.splitext(filename_with_extension)
		return filename
	
def basenames(file_list):
	def last_component(file_path):
		path_components = file_path.split("/")
		if len(path_components)>0:
			component = path_components[-1]
			if len(component)>0:
				return component
			elif len(path_components)>1:
				return path_components[-2]
		return "";	
	basenames = [last_component(file_path) for file_path in file_list]
	basenames = [remove_extension(file_path) for file_path in basenames]
	return basenames
	
def get_normed_reference(log_reference):
	lc_log_reference = log_reference.lower()
	return remove_extension(lc_log_reference)
		
def check_log_message(log_message):
	return len(log_message)>0

def check_log_reference(log_reference):
	return len(log_reference)>0

def check_project_reference(project_reference):
	if len(project_reference)<=0:
		return False

	lc_project_reference = project_reference.lower();
	if lc_project_reference == 'definition' or lc_project_reference == 'version':
		return True
	if lc_project_reference == 'plugin' or lc_project_reference == 'platform' or lc_project_reference == 'build':
		return True

	if (re.match('OP(\s*)\d\d\d\d+', project_reference, re.IGNORECASE) == None):
		return False

	return True;

def check_referencable_referenced(referencables, log_reference):
	lc_log_reference = get_normed_reference(log_reference)
	lc_referencables = [reference.lower() for reference in referencables]
	for referencable in lc_referencables:
		if lc_log_reference in referencable:
			return True
	return False

def check_valid_commit(look_cmd, log_message) :
	if not check_log_message(log_message):
		sys.stderr.write("[ERROR] Empty commit messages are not allowed")
		return False

	log_reference = get_log_reference(log_message)
	if not check_log_reference(log_reference):
		sys.stderr.write("[ERROR] Commit message does not contain a commit reference => [main-modification-file] ...")
		return False

	project_reference = get_project_reference(log_message)
	if not check_project_reference(project_reference):
		sys.stderr.write("[ERROR] Commit message does not reference aspect (definition|version|plugin|platform|build) or a project ticket => [main-modification-file](<ticket-number>) ...")
		return False

	changed_files = get_changed_files(look_cmd)
	if len(changed_files) != 0:
		referencables= basenames(changed_files)
		if not check_referencable_referenced(referencables, log_reference):
			sys.stderr.write("[ERROR] Commit message reference [%s] not contained in modified files %s" % (log_reference,str(referencables)))
			return False
	else:
		sys.stdout.write("[PRE-COMMIT PASSTHROUGH] No modified files were detected")
	
	return True
	
def run(command, use_revision, operation_id, message):
	log_message = ""
	look_cmd = command
		
	if use_revision:		
		look_cmd = look_cmd % ("%s", "-r", operation_id)
	else:
		look_cmd = look_cmd % ("%s", "-t", operation_id)
		
	if  message is None:
		log_message = get_log_message(look_cmd)	
	else:
		log_message = message

	if check_valid_commit(look_cmd, log_message):
		return 0
	return 1


def mainold():
	usage = "usage: %prog <repository-path> [options]"
	parser = OptionParser(usage=usage)

	parser.add_option("-r", "--revision", dest="revision", help="revision id, required if transaction id is not specified", metavar="REVISION_ID", default=None)
	parser.add_option("-t", "--transaction", dest="transaction", help="transaction id, required if revision id is not specified", metavar="TRANSACTION_ID", default=None)	
	parser.add_option("-m", "--message", dest="message", help="log message, used for dry runs against revision id's", metavar="LOG_MESSAGE", default=None)
	
	(opts, args) = parser.parse_args()
	
	if(len(args)<=0):
		sys.stderr.write("[ERROR] Log message check missing required repository path argument.")
		parser.print_help()
		return 1
	
	if opts.revision is None and opts.transaction is None:
		sys.stderr.write("[ERROR] Either revision id or transaction id must be specified.")
		parser.print_help()
		return 1
	
	look_cmd = "svnlook %s %s %s %s"  % ("%s", args[0], "%s", "%s")
	use_revision = opts.transaction is None
	operation_id = opts.revision if use_revision else opts.transaction
	return run(look_cmd, use_revision, operation_id, opts.message)

def main():
	usage = "usage: %prog <repository-path> [options]"
	parser = OptionParser(usage=usage)

	parser.add_option("-m", "--message", dest="message", help="log message, used for dry runs against revision id's", metavar="LOG_MESSAGE", default=None)
	
	(opts, args) = parser.parse_args()
	
	sys.stdout.write(opts.message);
	sys.stdout.write("\n");
	sys.stdout.write(get_project_reference(opts.message));	
	return 0;

if __name__ == "__main__":
	sys.exit(main())
