#!/cust/perl/bin/perl -w
# The Big Brother Watcher Daemon
#
# bbwd.pl --setsid=1 --log_file=/cust/bbh/watcher/bbwd.log --pid_file=/cust/bbh/watcher/bbwd.pid --port=8585
#    # To turn off the daemon, do:
#    kill `cat /tmp/samplechat.pid`;
#
#  To Do:
#	ability to list all connected clients and selectively kill them

package BigBrotherWatcherDaemon;

use strict;
use base qw(Net::Server::Multiplex);

__PACKAGE__->run();
exit;

###----------------------------------------------------------------###

sub allow_deny_hook {
  my $self = shift;
  my $prop = $self->{server};
  my $sock = $prop->{client};

#  return 1 if $prop->{peeraddr} =~ /^127\./;
#  return 0;
  return 1;
}


sub request_denied_hook {
  print "Go away!\n";
  print STDERR "DEBUG: Client denied!\n";
}


# IO::Multiplex style callback hook
sub mux_connection {
  my $self = shift;
  my $mux  = shift;
  my $fh   = shift;
  my $peer = $self->{peeraddr};
  # Net::Server stores a connection counter in the {requests} field.
  $self->{id} = $self->{net_server}->{server}->{requests};
  # Keep some values that I might need while the {server}
  # property hash still contains the current client info
  # and stash them in my own object hash.
  $self->{peerport} = $self->{net_server}->{server}->{peerport};
  # Net::Server directs STDERR to the log_file
  print STDERR "DEBUG: Client [$peer] (id $self->{id}) just connected...\n";
  print $fh "Connection established!";

#  if ($peer =~ /^127\./) {
#    # Notify everyone that the client arrived
#    $self->broadcast($mux,"JOIN: (#$self->{id}) from $peer\r\n");
#    # STDOUT is tie'd to the correct IO::Multiplex handle
#    print "Welcome, you are number $self->{id} to connect.\r\n";
#  } else {
#    #dunno
#  }

}


# If this callback is ever hooked, then the mux_connection callback
# is guaranteed to have already been run once (if defined).
sub mux_input {
  my $self = shift;
  my $mux  = shift;
  my $fh   = shift;
  my $in_ref = shift;  # Scalar reference to the input
  my $peer = $self->{peeraddr};
  my $id   = $self->{id};

  print STDERR "DEBUG: input from [$peer]: $$in_ref\n";
  # Process each line in the input, leaving partial lines
  # in the input buffer
  while ($$in_ref =~ s/^(.*?)\r?\n//) {
    next unless $1;
#    my $message = "[$id - $peer] $1\r\n";

    my $message = $1;
    if ($peer =~ /^127\./) {
      $self->broadcast($mux, $message);
    } else {
    # Parse commands from the clients
      if ($message =~ /close/) {
        print $fh "Closing session . . .\n\r";
#        close socket
      }
      print STDERR "DEBUG: [$id - $peer] $message\r\n";
    }

#    print " - sent ".(length $message)." byte message\r\n";
  }
}


# It is possible that this callback will be called even
# if mux_connection or mux_input were never called.  This
# occurs when allow_deny or allow_deny_hook fails to
# authorize the client.  The callback object will be the
# default listen object instead of a client unique object.
# However, both object should contain the $self->{net_server}
# key pointing to the original Net::Server object.
sub mux_close {
  my $self = shift;
  my $mux  = shift;
  my $fh   = shift;
  my $peer = $self->{peeraddr};
  # If mux_connection has actually been run
  if (exists $self->{id}) {
#    $self->broadcast($mux,"LEFT: (#$self->{id}) from $peer\r\n");
    print STDERR "DEBUG: Client [$peer] (id $self->{id}) closed connection!\n";
  }
}

# Routine to send a message to all clients in a mux.
sub broadcast {
  my $self = shift;
  my $mux  = shift;
  my $msg  = shift;
  foreach my $fh ($mux->handles) {
    # NOTE: All the client unique objects can be found at
    # $mux->{_fhs}->{$fh}->{object}
    # In this example, the {id} would be
    #   $mux->{_fhs}->{$fh}->{object}->{id}
    print $fh $msg;
  }
}

sub send_alert {
  my $self = shift;
  my $mux  = shift;
  my $msg  = shift;
  foreach my $fh ($mux->handles) {
    unless ($mux->{_fhs}->{$fh}->{object}->{peeraddr} =~ /^127\./) {
      print $fh $msg;
    }
  }
}
