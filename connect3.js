const CDP = require('chrome-remote-interface');
const { sleep } = require('simple-sleep');

const wsEndpoint = process.argv[2];
if (!wsEndpoint) {
    console.log("Please provide a WS endpoint");
    return;
}

CDP({ target: wsEndpoint }, async(client) => {
    const {Debugger, Runtime} = client;
    try {
        client.Debugger.paused((event) => {
            console.log("Paused.", event);
            // client.Debugger.resume();
            // client.close();
        });
        await client.Runtime.runIfWaitingForDebugger();
        await client.Debugger.enable();
        while (true) {
            await sleep(1000);
        }
    } catch (err) {
        console.error(err);
    } finally {
        client.close();
    }
}).on('error', (err) => {
    console.error(err);
});