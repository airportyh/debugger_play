const CDP = require('chrome-remote-interface');
const { sleep } = require('simple-sleep');

async function example() {
    let client = await CDP({ target: 'ws://localhost:9222/devtools/page/67B5E01C71F84CF84A24F95748444DCB' });
    const { Network, Page, Target, Debugger, Runtime } = client;
    // Network.requestWillBeSent((params) => {
    //     console.log(params.request.url);
    // });
    // await Network.enable();
    await Page.enable();
    // await Page.navigate({url: 'https://github.com'});
    // await Page.loadEventFired();
    // const reply = await Target.getTargets();
    // const target = reply.targetInfos[1];
    // const targetId = target.targetId;
    // 
    // await Target.activateTarget({ targetId });
    await Page.bringToFront();
    await Page.reload();
    // await Page.navigate({ url: 'file:///Users/airportyh/Home/Playground/myDebugger/index.html' });
    console.log("done navigating");
    Page.waitForDebugger();
    console.log("done waiting for debugger");
    await sleep(5000);
    console.log("going");
    await Runtime.runIfWaitingForDebugger();
    console.log("enabling debugger");
    await Debugger.enable();
    console.log("stepping");
    // await Debugger.stepOver();
    client.close();
    
}

example().catch(console.error);