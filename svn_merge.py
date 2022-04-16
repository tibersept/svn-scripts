
# An extended SVN merge which is useful for commits using a ticketing system

# sample call:
# python merge.py --revision=85000 --range=8000:9000

import sys, re
import modules.MergeRevision as TicketMerge

config = {
	
	# repository locations
	# "repo" - repo location
	# "trunk" - source location
	"svn_env": {
		"trunk": "/trunk/<project-name>"
	},

	# repo locations
	# "repo" - your repo path
	# "local" - your local repo path
	"svn_location": {
		"repo": "https://<svn_host>:<svn_port>/svn/<project_name>/",
		"local": "<path_to_project>"
	},

	# List of file paths starting from the root of the project that will be ignored
	# when collisions are detected for these files
	"ignore_file_list": [
		"/WebContent/index.html"
	],

	# just somewhere to dump logs  
	"temp_folder": "<path_to_temp_folder>"

}

# start
svn = TicketMerge.create(config)
svn.execute()
