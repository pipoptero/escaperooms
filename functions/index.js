"use strict";

const { onCall, HttpsError } = require("firebase-functions/v2/https");
const { initializeApp } = require("firebase-admin/app");
const { getDatabase } = require("firebase-admin/database");
const moderation = require("./scream-review-moderation");

// The emulator's implicit legacy database URL differs from its default RTDB
// instance. Point only emulator calls at the same instance used by rules tests.
const emulatorOptions = process.env.FUNCTIONS_EMULATOR === "true"
  ? { databaseURL: `https://${process.env.GCLOUD_PROJECT}-default-rtdb.firebaseio.com` }
  : {};
initializeApp(emulatorOptions);

function callable(handler) {
  return onCall({ region: "europe-west1", enforceAppCheck: true, maxInstances: 2,
    timeoutSeconds: 30 }, async request => {
    try { return await handler(request, getDatabase()); }
    catch (error) {
      const code = ["unauthenticated", "permission-denied", "invalid-argument", "failed-precondition"].includes(error.code)
        ? error.code : "internal";
      throw new HttpsError(code, code === "internal" ? "Moderation unavailable" : error.message);
    }
  });
}

exports.listScreamParkReviewQueue = callable(moderation.listPending);
exports.moderateScreamParkReview = callable(moderation.decide);
exports.submitScreamParkReview = callable(moderation.submit);
exports.deleteScreamParkReview = callable(moderation.deleteOwn);
