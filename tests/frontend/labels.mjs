import { pathToFileURL } from "node:url";

const { shortLabel } = await import(pathToFileURL(process.argv[2]).href);
if (process.argv[3] === "fallback") {
  // Names without a register label: [friendly name, device name] pairs.
  const cases = [
    ["Controller  Temperature", "Controller"],
    ["Controller Temperature", "Controller"],
    ["Controller Supply Temperature", "Controller"],
    ["Controller", "Controller"],
    ["Temperature", undefined],
  ];
  console.log(JSON.stringify(cases.map(([name, device]) => shortLabel({ language: "en" }, "input_9999", name, device))));
} else {
  console.log(JSON.stringify(["en", "de"].map(language => shortLabel({ language }, "input_43"))));
}
console.log("HARNESS-COMPLETE");
