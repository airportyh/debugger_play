const WebSocket = require('ws');

main().catch(console.error);

async function main() {
  const wsEndpoint = process.argv[2];
  if (!wsEndpoint) {
      console.log("Please provide a WS endpoint.");
      return;
  }

  // Create a websocket to issue CDP commands.
  const ws = new WebSocket(wsEndpoint, {perMessageDeflate: false});
  await new Promise(resolve => ws.once('open', resolve));
  console.log('connected!');

  ws.on('message', msg => console.log(msg.toString()));

  console.log('Sending Target.setDiscoverTargets');
  ws.send(JSON.stringify({
    id: 1,
    method: 'Target.setDiscoverTargets',
    params: {
      discover: true
    },
  }));
}

