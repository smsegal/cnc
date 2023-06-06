# CNC

CNC is a tool that combines WakeOnLan (WoL) and SSH to wake up a big power-hungry host, and then connect to it.

This is trivial when you are on the same local network, as you can just send out the magic wakeonlan packet.
But it's significantly more complicated when not on the same network.

CNC gets around this by making one assumption about your local network topology.

There must exist an always-on host on the same network as the big power-hungry host that is accesible from the internet.
This host is connected to first, and then sends the magic packet.
At this point, we wait for the sleeping host to wake up, and then connect to it via SSH.