# Firestore Security Rules

Use this as the canonical production ruleset for this repository.

Firebase Console path:

1. Firestore Database -> Rules
2. Replace existing rules
3. Publish

```text
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    function signedIn() {
      return request.auth != null;
    }

    function isOwner(userId) {
      return signedIn() && request.auth.uid == userId;
    }

    match /users/{userId} {
      // Keep parent doc locked unless you explicitly use it.
      allow read, write: if false;

      match /transactions/{txnId} {
        allow read, write: if isOwner(userId);
      }

      match /holdings/{holdingId} {
        allow read, write: if isOwner(userId);
      }

      match /meta/{metaId} {
        allow read, write: if isOwner(userId);
      }
    }

    // Shared union index for scheduler and authenticated client reads.
    match /active_products/{docId} {
      allow read: if signedIn();
      allow write: if false;
    }

    // Shared mapping metadata used by product search/autocomplete.
    match /product_mappings/{docId} {
      allow read, write: if signedIn();
    }

    // Default deny for anything not explicitly allowed above.
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

## Rule Summary

1. Users can only access their own `users/{uid}/...` subcollections.
2. `active_products` is read-only from clients.
3. `product_mappings` is available to authenticated users.
4. Everything else is denied by default.

## Validation Checklist

Use Rules Simulator:

1. Read `users/userA/transactions/x` as `userA` -> allow
2. Read `users/userB/transactions/x` as `userA` -> deny
3. Write `active_products/any` as authenticated user -> deny
4. Write `product_mappings/any` as authenticated user -> allow

