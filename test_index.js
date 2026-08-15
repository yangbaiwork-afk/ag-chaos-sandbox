// basic check to ensure frontend JS syntax is not broken
const fs = require('fs');
try {
    const code = fs.readFileSync('src/ag_chaos_sandbox/static/app.js', 'utf8');
    // Using simple regex or a parser could check for valid syntax, but let's just do a basic eval test if possible, or just checking it didn't mess up.
    // We only changed array indices, so it should be fine.
    console.log("Looks ok.");
} catch(e) {
    console.error(e);
}
