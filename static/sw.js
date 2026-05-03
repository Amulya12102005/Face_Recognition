self.addEventListener("install", () => {
  console.log("Service Worker Installed");
});

self.addEventListener("fetch", (event) => {
  // you can add caching later
});