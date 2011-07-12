#!/cust/perl/bin/perl -w
#
# Usage: ./send-test-event-tcp.pl red hostname conn 1

use IO::Socket;
my $sock = new IO::Socket::INET (
PeerAddr => 'localhost',
PeerPort => '8585',
Proto => 'tcp',
);
die "Error: $!\n" unless $sock;

my $data = "$ARGV[0] $ARGV[1] $ARGV[2] $ARGV[3]";
print $sock "$data\n";
close($sock);
print scalar localtime, ": $data\n";
exit;
