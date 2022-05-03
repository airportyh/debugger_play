const { sleep } = require("simple-sleep");

async function doIt() {
    let sum = 0;
    let i = 1;
    while (true) {
        await sleep(1000);
        sum += i;
        console.log(sum);
        i++;
    }
}

doIt().catch(console.log);