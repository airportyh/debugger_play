const CDP = require('chrome-remote-interface');

main().catch(console.error);

async function main() {
    const wsEndpoint = process.argv[2];
    if (!wsEndpoint) {
        console.log("Please provide a WS endpoint");
        return;
    }
    let client = await CDP({ target: wsEndpoint });
    client.on('event', (event) => {
        console.log("event", event);
    });
    await client.Debugger.enable();
    while (true) {
        await sleep(1000);
    }
}

function sleep(ms) {
    return new Promise((accept) => {
        setTimeout(() => accept(), ms);
    });
}

