const CDP = require('chrome-remote-interface');
const { sleep } = require('simple-sleep');

async function main() {
    let client;
    try {
        // connect to endpoint
        client = await CDP();
        const { Debugger } = client;
        // extract domains
        client.on('event', (event) => {
            console.log("event", event);
        });
        let reply = await Debugger.enable();
        console.log(reply);
        reply = await Debugger.stepInto();
        console.log(reply);
        while (true) {
            await sleep(1000);
        }
        
    } catch (err) {
        console.error(err);
    } finally {
        if (client) {
            await client.close();
        }
    }
}

main();