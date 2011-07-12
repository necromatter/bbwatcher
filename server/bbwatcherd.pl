#!/cust/perl/bin/perl -w
use POSIX;
use IO::Socket;
use IO::Select;
use Fcntl;
use Tie::RefHash;
use Carp;

$port = 8585;
$eventdata = '';
#$bbwatcherpath="/cust/bbh/watcher";
$bbwatcherdLog="/cust/bbh/watcher/bbwatcherd.log";

# Test to make sure there is no deamon process or pid file.
if (-e "/cust/bbh/watcher/bbwatcherd.pid") {
	die "bbwatcherd is running or the pid file was not removed: $!";
}

# Redirect output for the daemon process.
print scalar localtime, ": Launching initial process $$.\n";
open(LOGFILE, ">>$bbwatcherdLog") or die "Couldn't open logfile: $!";
chdir '/'                   or die "Can't chdir to /: $!";
open (STDIN, '/dev/null')   or die "Can't read /dev/null: $!";
open (STDOUT, ">>&LOGFILE") or die "Can't write to $bbwatcherdLog: $!";
open (STDERR, ">>&LOGFILE") or die "Can't write to $bbwatcherdLog: $!";
nonblock(STDIN);
nonblock(STDOUT);
nonblock(STDERR);

# Daemonize the program. This redirects IO to log files.
defined(my $pid = fork)    || die "Can't fork: $!";
exit if $pid;
setsid                     || die "Can't start a new session: $!";
umask 0;
print scalar localtime, ": Big Brother Watcher daemonized as process $$.\n";

# Write the pid to a pidfile.
open(PIDFILE, "> /cust/bbh/watcher/bbwatcherd.pid")
  or die "Couldn't open pidfile";
  print PIDFILE $$;
close(PIDFILE);

# Listen to port.
$server = IO::Socket::INET->new(LocalPort => $port,
                                Listen    => 10,
				Reuse     => 1 )
  || die "Can't make server socket: $@\n";

# Begin with empty buffers.
%inbuffer  = ( );
%outbuffer = ( );
%ready     = ( );

tie %ready, 'Tie::RefHash';

nonblock($server);
$select = IO::Select->new($server);
$select->add($server);
# Trap signals so we can exit gracefully.
$time_to_die = 0;
sub signal_handler {
    $time_to_die = 1;
}
$SIG{INT} = $SIG{TERM} = $SIG{HUP} = \&signal_handler;
# trap or ignore $SIG{PIPE}
$SIG{PIPE} = 'IGNORE';


# Spawn the local unix socket for event data.
BEGIN { $ENV{PATH} = '/usr/ucb:/bin' }
sub spawn;  # forward declaration
sub logmsg { print scalar localtime, ": \[$$\] @_\n" }

my $SOCK = '/cust/bbh/watcher/bbwatcherd.sock';
my $uaddr = sockaddr_un($SOCK);
my $proto = getprotobyname('tcp');

socket(Server,PF_UNIX,SOCK_STREAM,0)        || die "socket: $!";
unlink($SOCK);
bind  (Server, $uaddr)                      || die "bind: $!";
chmod(0666, $SOCK);
listen(Server,SOMAXCONN)                    || die "listen: $!";

nonblock(Server);
Server->autoflush(1);

logmsg "Local UNIX socket opened: $SOCK";

my $waitedpid;

use POSIX ":sys_wait_h";
sub REAPER {
    my $child;
    while (($waitedpid = waitpid(-1,WNOHANG)) > 0) {
#        logmsg "reaped $waitedpid" . ($? ? " with exit $?" : '');
    }
    $SIG{CHLD} = \&REAPER;  # loathe sysV
}

$SIG{CHLD} = \&REAPER;

sub spawn {
    my $coderef = shift;

    unless (@_ == 0 && $coderef && ref($coderef) eq 'CODE') {
        confess "usage: spawn CODEREF";
    }

    my $pid;
    if (!defined($pid = fork)) {
        logmsg "cannot fork: $!";
        return;
    } elsif ($pid) {
#        logmsg "begat $pid";
        my $eventdata = <Client>;
        #print "Eventdata: $eventdata\n";
        logmsg "Event: \"$eventdata\"";
        return $eventdata; # I'm the parent
    }
    # else I'm the child -- go spawn

    open(STDIN,  "<&Client")   || die "can't dup client to stdin";
    open(STDOUT, ">&Client")   || die "can't dup client to stdout";
    nonblock(STDIN);
    nonblock(STDOUT);
    open(STDERR, ">&STDOUT") || die "can't dup stdout to stderr";
    exit &$coderef();
}
# End spawn process.

# Main loop: check reads/accepts, check writes, check ready to process
while(1) {
    my $client;
    my $newclient;
    my $rv;
    my $data;

    ### Read in data from the local unix socket
    for ( $waitedpid = 0;
        accept(Client,Server) || $waitedpid;
        $waitedpid = 0, close Client)
    {
        next if $waitedpid;
#        logmsg "connection on $SOCK";
#        print Client "First response from server.";

#        $eventdata = spawn sub {
#             print Client "Data sent to server at ", scalar localtime, "\n";
#        };
#        print "Returnline: $eventdata\n";
    }

# check for new information on the connections we have

# anything to read or accept?
    foreach $client ($select->can_read(1)) {

        if ($client == $server) {
            # accept a new connection

            $newclient = $server->accept( );
            $select->add($newclient);
            nonblock($newclient);
            fcntl($newclient, F_SETFL(), SO_KEEPALIVE);

            # find out who connected
            my ($client_host,$client_ipnum,$client_port) = &client_info($newclient);
            print "Client connection from: $client_host\[$client_ipnum\] port $client_port\n"; 
        } else {
            # read data
            $data = '';
            $rv   = $client->recv($data, POSIX::BUFSIZ, 0);

            my ($client_host,$client_ipnum,$client_port) = &client_info($client);
#	    print "Data from $client_host: $data\n";

	    # Look for a 'close' packet to be sent from the client.
	    if ($data eq "close") {
		$outbuffer{$client} = "Closing session . . .";
	    } else {
		$outbuffer{$client} = "Connection established!";
	    }

            unless (defined($rv) && length $data) {
                # This would be the end of file, so close the client
                delete $inbuffer{$client};
                delete $outbuffer{$client};
                delete $ready{$client};

                $select->remove($client);
                close $client;
                next;
            }

            $inbuffer{$client} .= $data;

            # test whether the data in the buffer or the data we
            # just read means there is a complete request waiting
            # to be fulfilled.  If there is, set $ready{$client}
            # to the requests waiting to be fulfilled.
            while ($inbuffer{$client} =~ s/(.*\n)//) {
                push( @{$ready{$client}}, $1 );
            }
        }
    }

    # Any complete requests to process?
#    foreach $client (keys %ready) {
#        handle($client);
#    }

    # Buffers to flush?
    foreach $client ($select->can_write(1)) {
	if ( $eventdata )
        {
	    $outbuffer{$client} = $eventdata;
	}
        if ($time_to_die)
        {
            $outbuffer{$client} = "Server quitting";
        }
        # Skip this client if we have nothing to say
        next unless exists $outbuffer{$client};

        $rv = $client->send($outbuffer{$client}, 0);
        unless (defined $rv) {
            # Whine, but move on.
            warn "I was told I could write, but I can't.\n";
            next;
        }
        if (($rv == length $outbuffer{$client} ||
            $!  == POSIX::EWOULDBLOCK) && !$time_to_die)  
        {
            substr($outbuffer{$client}, 0, $rv) = '';
            delete $outbuffer{$client} unless length $outbuffer{$client};
        } else {
            # Couldn't write all the data, and it wasn't because
            # it would have blocked.  Shutdown and move on.
            delete $inbuffer{$client};
            delete $outbuffer{$client};
            delete $ready{$client};

            $select->remove($client);
            close($client);
            next;
        }
    }
    # Clear the eventdata after sending to all clients
    $eventdata = '';

    # Out of band data?
    foreach $client ($select->has_exception(0)) {  # arg is timeout
        # Deal with out-of-band data here, if you want to.
    }
    if ($time_to_die)
    {
	print "Recieved exit signal...\n";
	unlink("/cust/bbh/watcher/bbwatcherd.pid");
	unlink("/cust/bbh/watcher/bbwatcherd.sock");
	close(LOGFILE);
	exit 0;
    }
}


# handle($socket) deals with all pending requests for $client
sub handle {
    # requests are in $ready{$client}
    # send output to $outbuffer{$client}
    my $client = shift;
    my $request;

    foreach $request (@{$ready{$client}}) {
        # $request is the text of the request
        # put text of reply into $outbuffer{$client}
    }
    delete $ready{$client};
}

# nonblock($socket) puts socket into nonblocking mode
sub nonblock {
    my $socket = shift;
#    my $flags;
    
#    $flags = fcntl($socket, F_GETFL, 0)
#            or die "Can't get flags for socket: $!\n";
    fcntl($socket, F_SETFL(), O_NONBLOCK())
            or die "Can't make socket nonblocking: $!\n";
}

sub client_info {
   my $sock = shift;
   my ($remote_addr,$port,$ip,$rname);

   $remote_addr = getpeername($sock);
   ($port,$ip) = sockaddr_in($remote_addr);
   $rname = gethostbyaddr($ip,AF_INET) || $ip;
   $ipnum = inet_ntoa($ip);
   return ($rname,$ipnum,$port);
}
