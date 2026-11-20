import { pathToFileURL } from "node:url";

const { shortLabel } = await import(pathToFileURL(process.argv[2]).href);
console.log(JSON.stringify(["en", "de"].map(language => shortLabel({ language }, "input_43"))));
console.log("HARNESS-COMPLETE");
