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

my $color = $ENV{BBCOLORLEVEL};
my $host = $ENV{BBHOSTNAME};
my $svc = $ENV{BBSVCNAME};

# Find the Priority level of the service, if configured
$nkconf = "/cust/bb/server/etc/hobbit-nkview.cfg";
my $PRIO = "NA";
 
open (CONFFILE,"$nkconf") || die "Error opening nkconf file $nkconf.\n";
 
while(<CONFFILE>)
{
  if (/^$host\|$svc\|.+/)
  {
    my @line = split /\|/;
    $PRIO = $line[5];
    last;
  }
  elsif (/^$host\|\=(.+)$/)
  {
    open (CONFFILEA,"$nkconf") || die "Error opening nkconf file $nkconf.\n";
    while(<CONFFILEA>)
    {
      if (/^$1\|$svc\|.+/)
      {
        my @line = split /\|/;
        $PRIO = $line[5];
        last;
      }
    }
    close (CONFFILEA);
    last;
  }
}
close (CONFFILE);

my $data = "$color $host $svc $PRIO";
print $sock "$data\n";
close($sock);
#print scalar localtime, ": $data\n";
exit;
