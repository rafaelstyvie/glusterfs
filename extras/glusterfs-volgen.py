#!/usr/bin/python
                                                              
import getopt, sys, os, string

transport_type = "tcp"
gfs_port = 6996
raid_type = None
num_replica = 2
num_stripe = 4
cache_size = "1GB"

def print_usage (name):
    print name, " --name <volume-name> "
    print "    [--raid 0|1|10] "
    print "    [--transport tcp|ib-verbs] "
    print "    [--cache-size <cache-size>] "
    print "    [--port <port>] "
    print "    [--export-directory <export-dir>] "
    print "    [--num-stripe n] "
    print "    [--num-replica m] "
    print "    [--usage] "
    print "    [--upgrade] "
    print "    host1 host2 ... hostN "
    return

def setup_env ():
#    os.system ("mkdir -p "confdir"/glusterfs")
#    os.system ("touch "confdir"/glusterfs/19993")
    return

def print_mount_volume (mount_fd, servers):

    global raid_type
    global gfs_port
    global transport_type
    global num_replica
    global num_stripe
    global cache_size
    
    # Make sure 'server list is uniq'
    tmp_servers = []
    for server in servers:
        if server in tmp_servers:
            print "duplicate entry in server list (%s).. exiting" % server
            sys.exit (1)
        tmp_servers.append (server);

    num_servers = len (servers)
    
    if num_servers is 0:
        print "no servers given, exiting"
        sys.exit (1)

    # Make sure proper RAID type is given
    if raid_type == 1:
        if (num_servers % num_replica) != 0:
            print "raid type (%d) and number of of hosts (%d) not appropriate" % (raid_type, num_servers)
            sys.exit (1)
        num_stripe = 1
        
    if raid_type == 0:
        if (num_servers % num_stripe) != 0:
            print "raid type (%d) and number of of hosts (%d) not appropriate" % (raid_type, num_servers)
            sys.exit (1)
        num_replica = 1

    if raid_type == 10:
        if (num_servers % (num_replica * num_stripe)) != 0:
            print "raid type (%d) and number of of hosts (%d) not appropriate" % (raid_type, num_servers)
            sys.exit (1)

    cmdline = string.join (sys.argv, ' ')
    mount_fd.write ("## file auto generated by %s (mount.vol)\n" % sys.argv[0])
    mount_fd.write ("# Cmd line:\n")
    mount_fd.write ("# $ %s\n\n" % cmdline)

    if raid_type is not None:
        # Used for later usage
        mount_fd.write ("# RAID %d\n" % raid_type)

    mount_fd.write ("# TRANSPORT-TYPE %s\n" % transport_type)
    mount_fd.write ("# PORT %d\n\n" % gfs_port)

    for host in servers:
        mount_fd.write ("volume %s\n" % host)
        mount_fd.write ("    type protocol/client\n")
        mount_fd.write ("    option transport-type %s\n" % transport_type)
        mount_fd.write ("    option remote-host %s\n" % host)
        mount_fd.write ("    option remote-port %d\n" % gfs_port)
        mount_fd.write ("    option remote-subvolume brick\n")
        mount_fd.write ("end-volume\n\n")

    subvolumes = []
    subvolumes.append (host)
    
    # Stripe section.. if given
    if raid_type is 0 or raid_type is 10:
        subvolumes = []
        temp = []
        flag = 0
        for host in servers:
            temp.append (host)
            flag += 1
            if (flag % num_stripe) is 0:
                subvolumes.append (string.join (temp, ' '))
                temp = []

        max_stripe_idx = len (servers) / num_stripe
        stripe_idx = 0
        while stripe_idx < max_stripe_idx:
            mount_fd.write ("volume stripe-%d\n" % stripe_idx)
            mount_fd.write ("    type cluster/stripe\n")
            mount_fd.write ("    subvolumes %s\n" % subvolumes[stripe_idx])
            mount_fd.write ("end-volume\n\n")
            stripe_idx += 1

    # Replicate section
    if raid_type is 1 or raid_type is 10:
        if raid_type is 1:
            subvolumes = []
            temp = []
            flag = 0
            for host in servers:
                temp.append (host)
                flag += 1
                if (flag % num_replica) is 0:
                    subvolumes.append (string.join (temp, ' '))
                    temp = []
        else:
            subvolumes = []
            temp = []
            flag = 0
            while flag < stripe_idx:
                temp.append ("stripe-%d" % flag)
                flag += 1
                if (flag % num_replica) is 0:
                    subvolumes.append (string.join (temp, ' '))
                    temp = []
                    
        max_mirror_idx = len (servers) / (num_replica * num_stripe)
        mirror_idx = 0
        while mirror_idx < max_mirror_idx:
            mount_fd.write ("volume mirror-%d\n" % mirror_idx)
            mount_fd.write ("    type cluster/replicate\n")
            mount_fd.write ("    subvolumes %s\n" % subvolumes[mirror_idx])
            mount_fd.write ("end-volume\n\n")
            mirror_idx += 1

    # Distribute section
    if raid_type is None:
        subvolumes = []
        for host in servers:
            subvolumes.append (host)
            
    elif raid_type is 0:
        subvolumes = []
        flag = 0
        while flag < stripe_idx:
            subvolumes.append ("stripe-%d" % flag)
            flag += 1
    else:
        subvolumes = []
        flag = 0
        while flag < mirror_idx:
            subvolumes.append ("mirror-%d" % flag)
            flag += 1

    if len (subvolumes) > 1:
        mount_fd.write ("volume distribute\n")
        mount_fd.write ("    type cluster/distribute\n")
        mount_fd.write ("    subvolumes %s\n" % string.join (subvolumes, ' '))
        mount_fd.write ("end-volume\n\n")
        subvolumes[0] = "distribute"

    mount_fd.write ("volume writebehind\n")
    mount_fd.write ("    type performance/write-behind\n")
    mount_fd.write ("    option cache-size 4MB\n")
    mount_fd.write ("    subvolumes %s\n" % subvolumes[0])
    mount_fd.write ("end-volume\n\n")
    
    mount_fd.write ("volume io-cache\n")
    mount_fd.write ("    type performance/io-cache\n")
    mount_fd.write ("    option cache-size %s\n" % cache_size)
    mount_fd.write ("    subvolumes writebehind\n")
    mount_fd.write ("end-volume\n\n")

    return

def print_export_volume (exp_fd, export_dir):

    global transport_type
    global gfs_port

    cmdline = string.join (sys.argv, ' ')
    exp_fd.write ("## file auto generated by %s (export.vol)\n" % sys.argv[0])
    exp_fd.write ("# Cmd line:\n")
    exp_fd.write ("# $ %s\n\n" % cmdline)

    mount_fd.write ("# TRANSPORT-TYPE %s\n" % transport_type)
    mount_fd.write ("# PORT %d\n\n" % gfs_port)

    exp_fd.write ("volume posix\n")
    exp_fd.write ("  type storage/posix\n")
    exp_fd.write ("  option directory %s\n" % export_dir)
    exp_fd.write ("end-volume\n\n")

    exp_fd.write ("volume locks\n")
    exp_fd.write ("    type features/locks\n")
    exp_fd.write ("    subvolumes posix\n")
    exp_fd.write ("end-volume\n\n")

    exp_fd.write ("volume brick\n")
    exp_fd.write ("    type performance/io-threads\n")
    exp_fd.write ("    option thread-count 8\n")
    exp_fd.write ("    subvolumes locks\n")
    exp_fd.write ("end-volume\n\n")
    
    exp_fd.write ("volume server\n")
    exp_fd.write ("    type protocol/server\n")
    exp_fd.write ("    option transport-type %s\n" % transport_type)
    exp_fd.write ("    option auth.addr.brick.allow *\n")
    exp_fd.write ("    option listen-port %d\n" % gfs_port)
    exp_fd.write ("    subvolumes brick\n")
    exp_fd.write ("end-volume\n\n")
    
    return

def upgrade_mount_volume (volume_path, new_servers):

    global transport_type
    global gfs_port
    global raid_type
    
    try:
        tmp_read_fd = file (volume_path, "r")
    except:
        print "open failed"
        sys.exit (1)

    volume_file_buf = tmp_read_fd.readlines ()
    volume_file_buf = map (string.strip, volume_file_buf)

    old_servers = []
    for line in volume_file_buf:
        if line[0:6] == "# RAID":
            raid_type = int (line[7:])
        
        volume_name = ""
        if line[0:6] == "volume":
            volume_name = line[7:]
            if (volume_name == "stripe-0" or volume_name == "mirror-0" or volume_name == "distribute"):
                break
            old_servers.append (volume_name)
        
        if (len (line) > 22 and line[7:21] == "transport-type"):
            transport_type = line[22:]

        if (len (line) > 20 and line[7:18] == "remote-port"):
            gfs_port = int (line[19:])

        
    servers = old_servers + new_servers

    # Make sure 'server list is uniq'
    tmp_servers = []
    for server in servers:
        if server in tmp_servers:
            print "duplicate entry in server list (%s).. exiting" % server
            sys.exit (1)
        tmp_servers.append (server);
    
    try:
        tmp_fd = file (volume_path, "w")
    except:
        print "open failed"
        sys.exit (1)

    print_mount_volume (tmp_fd, servers)
    return


def main ():

    global transport_type
    global gfs_port
    global raid_type
    global num_replica
    global num_stripe
    
    main_name = None

    needs_upgrade = None
    version_num ="0.1.3"
    volume_name = None
    export_dir = None

    # TODO: take this variable from --prefix option.
    confdir = "/usr/local/etc/glusterfs" 
    
    #rport = $(($(ls ${confdir}/glusterfs/ | sort | head -n 1 | cut -f 1 -d -) - 10));
    #cache_size = "$(free | grep 'Mem:' | awk '{print $2 * .40}')KB"; # 40% of available memory

    export_volume_path="/dev/stdout"
    mount_volume_path="/dev/stdout"

    try:
        (opt, args) = getopt.getopt (sys.argv[1:], "r:t:c:p:d:n:uh",
                                     ["raid=",
                                      "transport=",
                                      "cache-size=",
                                      "port=",
                                      "export-directory=",
                                      "num-stripe=",
                                      "num-replica=",
                                      "name=",
                                      "upgrade",
                                      "usage",
                                      "help"])

    except getopt.GetoptError, (msg, opt):
        print msg
        sys.exit (1)
                        
    for (o, val) in opt:
        if o == '--usage' or o == '--help':
            print_usage (sys.argv[0])
            sys.exit (0)
            
        if o == '--upgrade':
            needs_upgrade = 1

        if o == '--num-stripe':
            num_stripe = int (val)
            
        if o == '--num-replica':
            num_replica = int (val)
            
        if o == '-n' or o == '--name':
            main_name = val
            
        if o == '-d' or o == '--export-directory':
            export_dir = val
            
        if o == '-p' or o == '--port':
            gfs_port = int (val)

        if o == '-c' or o == '--cache-size':
            cache_size = val

        if o == '-r' or o == '--raid':
            if (val != "1" and val != "0" and val != "10"):
                print "--raid: option " + val + " is not valid raid type"
                sys.exit (1)                
            raid_type = int (val)

        if o == '-t' or o == '--transport':
            if (val != "tcp" and val != "ib-verbs"):
                print "--transport: option " + val + " is not valid transport type"
                sys.exit (1)
            transport_type = val
    
    if main_name is None:
        print "'--name' option not given, exiting"
        sys.exit (1)

    setup_env()
    export_volume_path = "%s/%s-export.vol" % (confdir, main_name)
    mount_volume_path  = "%s/%s-mount.vol" % (confdir, main_name)

    num_servers = len (args)
    
    if num_servers is 0:
        print "no servers given, exiting"
        sys.exit (1)

    if needs_upgrade is 1:
        upgrade_mount_volume (mount_volume_path, args)
        sys.exit (0)

    if export_dir is None:
        print "'--export-directory' option not given, exiting"
        sys.exit (1)
        
    try:
        exp_fd = file (export_volume_path, "w")
    except:
        print "open failed"
        sys.exit (1)

    try:
        mount_fd = file (mount_volume_path, "w")
    except:
        print "open failed"
        sys.exit (1)

    print "printing volume files"
    print_export_volume (exp_fd, export_dir)
    print_mount_volume (mount_fd, args)
    return

main ()
