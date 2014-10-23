## vminventory: vCenter inventory update from .vmx files tool 

This command-line tool lets you update your vCenter inventory based on .vmx files not already linked to VMs.

Requirements
* linux or windows box
* Python 2.6 or higher
* [argparse](https://docs.python.org/3/library/argparse.html) library
* [pyvmomi](https://github.com/vmware/pyvmomi) library
* access to a VMWare vCenter host

Installation:
-------------
* Clone repository   
`git clone https://github.com/sebbrochet/vminventory.git`
* cd into project directory   
`cd vminventory`
* Install requirements with pip   
`pip install -r requirements.txt`
* Install vminventory binary   
`python setup.py install`

Usage:
------

```
usage: vminventory [-h] [-s SCOPE] [-u USER] [-p PASSWORD] [-t TARGET]
                   [-o PORT] [-r RESOURCEPOOL] [-f FOLDER] [-d DATACENTER]
                   [-c CONFIG] [-v]
                   command

vCenter inventory update from .vmx files tool.

positional arguments:
  command               Command to execute (add_to_inventory, list_folder,
                        list_orphaned_vm, list_resourcepool)

optional arguments:
  -h, --help            show this help message and exit
  -s SCOPE, --scope SCOPE
                        Limit command to act on scope defined in a file
  -u USER, --user USER  Specify the user account to use to connect to vCenter
  -p PASSWORD, --password PASSWORD
                        Specify the password associated with the user account
  -t TARGET, --target TARGET
                        Specify the vCenter host to connect to
  -o PORT, --port PORT  Port to connect on (default is 443)
  -r RESOURCEPOOL, --resourcepool RESOURCEPOOL
                        Specify the name of the resource pool to add VM in
  -f FOLDER, --folder FOLDER
                        Specify the name of the folder to add VM in (default
                        is 1st one)
  -d DATACENTER, --datacenter DATACENTER
                        Specify the datacenter name to run commands on
                        (default is all datacenters)
  -c CONFIG, --config CONFIG
                        Configuration file to use
  -v, --version         Print program version and exit.
```

`scope` of VM (vmx files) to be included in commands can be defined in a file by listing the short VM names, one by line.   
A line starting with a `#` is considered as comment and won't be interpreted.     

`config` format is one argument by line (i.e argname=value), argument names are the same ones than the CLI (scope, user, password, ...).   
A line starting with a `#` is considered as comment and won't be interpreted.    
Don't put quotes between argument values
