#!/usr/bin/env python
# -*- coding: utf-8 -*-

import atexit
from pyVim import connect
from pyVmomi import vim, vmodl
import time

import requests
requests.packages.urllib3.disable_warnings()

def myprint(unicodeobj):
    import sys
    print unicodeobj.encode(sys.stdout.encoding or 'utf-8')

def get_full_name(vm):
    current = vm
    full_name = vm.name

    while hasattr(current, 'parentVApp') and current.parentVApp:
        full_name = "%s/%s" % (current.parentVApp.name, full_name)
        current = current.parentVApp

    while hasattr(current, 'parent') and current.parent:
        full_name = "%s/%s" % (current.parent.name, full_name)
        current = current.parent

    return full_name


def get_friendly_name(entity):
    full_name = get_full_name(entity)

    parts = full_name.split('/')

    friendly_name = ""

    if len(parts) == 5:
        friendly_name = '%s/%s' % (parts[1], parts[3])
    elif len(parts) == 6:
        friendly_name = '%s/%s/%s' % (parts[1], parts[3], parts[5])

    return friendly_name 
    

def get_friendly_folder_name(folder):
    full_name = get_full_name(folder)

    parts = full_name.split('/')

    friendly_name = ""

    if len(parts) == 3:
        friendly_name = parts[1]
    elif len(parts) > 3:
        friendly_name = '%s/%s' % (parts[1], '/'.join(parts[3:]))

    return friendly_name


def get_service_instance(args):
    service_instance = None

    try:
        service_instance = connect.SmartConnect(host=args.target,
                                                user=args.user,
                                                pwd=args.password,
                                                port=int(args.port))
        atexit.register(connect.Disconnect, service_instance)
    except IOError as e:
        pass
    except vim.fault.InvalidLogin, e:
        raise SystemExit("Error: %s" % e.msg)
    except TypeError, e:
        raise SystemExit("Error: %s" % e.message) 

    if not service_instance:
        raise SystemExit("Error: unable to connect to target with supplied info.")

    return service_instance


def get_vm_from_scope_IFN(scope):
    if not scope:
        return None

    vms_from_scope = []

    f = file(scope, "r")
    lines = f.read().split('\n')
    for line in lines:
        if line.startswith('#'):
            continue
        value = line.strip()

	if value:
            vms_from_scope.append(value)

    return vms_from_scope


def is_in_datacenter(vm, datacenter_name):
    return datacenter_name == '' or get_full_name(vm).split('/')[1] == datacenter_name


def is_in_scope(vmfold, vms_from_scope):
    return vms_from_scope is None or vmfold in vms_from_scope


def get_all_vmx_data(target, service_instance, vms_from_scope, datacenter_name):
    def get_vmx_in_datastore(dsbrowser, dsname, datacenter, fulldsname):
        search = vim.HostDatastoreBrowserSearchSpec()
        search.matchPattern = "*.vmx"
        searchDS = dsbrowser.SearchDatastoreSubFolders_Task(dsname, search)
   
        while searchDS.info.state != "success":
            import time
            time.sleep(0.1)
  
        vmx_data_in_datastore = []

        for rs in searchDS.info.result:
            dsfolder = rs.folderPath
            for f in rs.file:
                try:
                    dsfile = f.path
                    vmfold = dsfolder.split("]")
                    vmfold = vmfold[1]
                    vmfold = vmfold[1:]
                    if vmfold[-1] == '/':
                        vmfold = vmfold[:-1]
                    if is_in_scope(vmfold, vms_from_scope):
                        vmx_data_in_datastore.append((target, vmfold, dsfile, datacenter, fulldsname))
                except Exception, e:
                    print "Caught exception : " + str(e)
                    return []

        return vmx_data_in_datastore 

    all_vmx_data = []

    content = service_instance.RetrieveContent()
    for datacenter in content.rootFolder.childEntity:
        if datacenter_name == '' or datacenter.name == datacenter_name:
            for ds in datacenter.datastore:
                all_vmx_data.extend(get_vmx_in_datastore(ds.browser, "[%s]" % ds.summary.name, datacenter.name, ds.summary.name))

    return all_vmx_data

def get_all_uuid_from_vmx_data(args, all_vmx_data):

    import urllib2, urlparse, base64

    def get_uuid_from_vmx_data(args, vmx_data):
        def url_fix(s, charset='utf-8'):
            if isinstance(s, unicode):
                s = s.encode(charset, 'ignore')
            scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
            path = urllib2.quote(path, '/%')
            qs = urllib2.quote(qs, ':&=')

            return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))

        username = args.user
        password = args.password

        target, vmfold, dsfile, datacenter, fulldsname = vmx_data
        vmx_url = "https://%s/folder/%s/%s?dcPath=%s&dsName=%s" % (target, vmfold, dsfile, datacenter, fulldsname) 
        request = urllib2.Request(url_fix(vmx_url))
        base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        try:
            result = urllib2.urlopen(request)
            vmx_file_lines = result.readlines()
    
            for line in vmx_file_lines:
                if line.startswith("displayName"):
                    dn = line
                elif line.startswith("vc.uuid"):
                    vcid = line

            uuid = vcid.replace('"', "")
            uuid = uuid.replace("vc.uuid = ", "")
            uuid = uuid.strip("\n")
            uuid = uuid.replace(" ", "")
            uuid = uuid.replace("-", "")
            newDN = dn.replace('"', "")
            newDN = newDN.replace("displayName = ", "")
            newDN = newDN.strip("\n")
        
            dspath = "%s/%s" % (fulldsname, vmfold)
            tempdsVM = [newDN, dspath]

        except urllib2.HTTPError, e:
            print "Exception while checking %s:\n%s" % (vmx_url, e)
            return None, "", "", ""

        return uuid, newDN, fulldsname, vmfold 

    uuid_from_vmx_data_dict = {}

    for vmx_data in all_vmx_data:
       uuid, datastore_vm, fulldsname, vmfold = get_uuid_from_vmx_data(args, vmx_data)
       if uuid:
           uuid_from_vmx_data_dict[uuid] = (datastore_vm, fulldsname, vmfold) 
    
    return uuid_from_vmx_data_dict


def get_all_uuid_from_vm(service_instance):
    uuid_from_vm_dict = {}

    content = service_instance.RetrieveContent()
    object_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)

    for vm in object_view.view:
        uuid = vm.config.instanceUuid
        uuid = uuid.replace("-", "")
        uuid_from_vm_dict[uuid] = vm.name 

    return uuid_from_vm_dict


def get_vmx_data_not_in_inventory(args):
    vmx_data_not_in_inventory = []

    service_instance = get_service_instance(args)
    vms_from_scope = get_vm_from_scope_IFN(args.scope)

    all_vmx_data = get_all_vmx_data(args.target, service_instance, vms_from_scope, args.datacenter)
    uuid_from_vmx_data_dict = get_all_uuid_from_vmx_data(args, all_vmx_data)
    uuid_from_vm_dict = get_all_uuid_from_vm(service_instance)

    uuid_from_vmx_data_set = set(uuid_from_vmx_data_dict.keys())
    uuid_from_vm_set = set(uuid_from_vm_dict.keys())

    missing_uuid_in_vm = uuid_from_vmx_data_set - uuid_from_vm_set

    for uuid in missing_uuid_in_vm:
        vmx_data_not_in_inventory.append(uuid_from_vmx_data_dict[uuid])

    return vmx_data_not_in_inventory

 
def cmd_list_orphaned_vm(args):
    print "Looking for orphaned VM..."
    
    vmx_data_not_in_inventory = get_vmx_data_not_in_inventory(args)

    if vmx_data_not_in_inventory:
        print "Orphaned VM found (Display name - [Datastore] Folder name)"
        for datastore_vm, fulldsname, vmfold in vmx_data_not_in_inventory:
            print "%s - [%s] %s" % (datastore_vm, fulldsname, vmfold)
    else:
        print "No orphaned VM found."


def get_resource_pool_IFP(args):
    import sys

    service_instance = get_service_instance(args)
    content = service_instance.RetrieveContent()
    object_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.ResourcePool], True)

    resourcepool = None

    for current_resourcepool in object_view.view:
        if get_friendly_name(current_resourcepool) == args.resourcepool.decode(sys.stdout.encoding or 'utf-8'):
            resourcepool = current_resourcepool
            break

    return resourcepool

        
def get_vm_folder_IFP(args):
    import sys

    service_instance = get_service_instance(args)
    content = service_instance.RetrieveContent()
    object_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.Folder], True)

    folder = None

    for current_folder in object_view.view:
        if 'VirtualMachine' in current_folder.childType:
            if not args.folder or (args.folder and get_friendly_folder_name(current_folder) == args.folder.decode(sys.stdout.encoding or 'utf-8')):
                folder = current_folder
                break

    return folder


def cmd_add_to_inventory(args):
    if not args.resourcepool:
        print "Error: resourcepool parameter is mandatory with the 'add_to_inventory' command."
        print "You can use the 'list_resourcepool' command to display them with a friendly name."
        return

    print "Checking if resourcepool parameter is OK..."
    resource_pool = get_resource_pool_IFP(args)

    if not resource_pool:
        print "Error: resourcepool '%s' not found" % args.resourcepool
        print "You can use the 'list_resourcepool' command to display them with a friendly name."
        return

    print "Checking if folder parameter is OK..."
    folder = get_vm_folder_IFP(args)

    if not folder:
        print "Error: folder '%s' not found" % args.folder
        print "You can use the 'list_folder' command to display them with a friendly name."
        return

    print "Looking for orphaned VM..."
 
    vmx_data_not_in_inventory = get_vmx_data_not_in_inventory(args)

    if vmx_data_not_in_inventory:
        for datastore_vm, fulldsname, vmfold in vmx_data_not_in_inventory:
            datastore_path = "[%s] %s/%s.vmx" % (fulldsname, vmfold, datastore_vm)
            status_str = "Adding '%s' in inventory '%s': " % (datastore_path, get_friendly_folder_name(folder))
            print status_str,

            import sys
            sys.stdout.flush()

            task = folder.RegisterVM_Task(path=datastore_path, asTemplate = False, pool=resource_pool)

            import time
            while task.info.state == vim.TaskInfo.State.running:
                time.sleep(0.1)

            if task.info.state == vim.TaskInfo.State.success:
                print "OK"
            else:
                print "NOK"
                print "Error: %s" % task.info.error
    else:
        print "No vmx files to add in inventory."     

def cmd_list_resourcepool(args):
    service_instance = get_service_instance(args)
    content = service_instance.RetrieveContent()
    object_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.ResourcePool], True)

    for resourcepool in object_view.view:
        if is_in_datacenter(resourcepool, args.datacenter): 
            print get_friendly_name(resourcepool)

def cmd_list_vm_folder_IFP(args):
    service_instance = get_service_instance(args)
    content = service_instance.RetrieveContent()
    object_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.Folder], True)

    for folder in object_view.view:
        if 'VirtualMachine' in folder.childType and is_in_datacenter(folder, args.datacenter):
            print get_friendly_folder_name(folder)
