const CDP = require('chrome-remote-interface');

async function example() {
    let client = await CDP();
    const { Network, Page, Target } = client;
    // Network.requestWillBeSent((params) => {
    //     console.log(params.request.url);
    // });
    await Network.enable();
    await Page.enable();
    await Page.navigate({url: 'https://github.com'});
    await Page.loadEventFired();
    const targets = await Target.getTargets();
    console.log(targets);
    
    client.close();
    
}

example().catch(console.error);