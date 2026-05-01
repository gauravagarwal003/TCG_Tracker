# Firestore Security Rules

Use this as the canonical production ruleset for this personal tracker.

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

    function isOwnerEmail() {
      return signedIn()
        && request.auth.token.email == 'gagarwal003@gmail.com';
    }

    function isOwner(userId) {
      return isOwnerEmail() && request.auth.uid == userId;
    }

    function validProductMappingShape() {
      return request.resource.data.keys().hasOnly([
        'name',
        'product_id',
        'group_id',
        'categoryId',
        'imageUrl',
        'url',
        'updated_at',
        'created_at'
      ])
      && request.resource.data.name is string
      && request.resource.data.name.size() > 0
      && request.resource.data.name.size() <= 200
      && request.resource.data.product_id is string
      && request.resource.data.group_id is string
      && request.resource.data.categoryId is number
      && request.resource.data.imageUrl is string
      && request.resource.data.url is string
      && request.resource.data.updated_at is string;
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

    // Shared mapping metadata used by product search/autocomplete.
    match /product_mappings/{docId} {
        allow read: if isOwnerEmail();
        allow write: if isOwnerEmail()
        && validProductMappingShape()
        && docId == (request.resource.data.group_id + '_' + request.resource.data.product_id);
    }

    // Default deny for anything not explicitly allowed above.
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

## Rule Summary

1. Only `gagarwal003@gmail.com` can read or write data.
2. The owner can only access their own `users/{uid}/...` subcollections.
3. `product_mappings` is readable and writable only by the owner with strict shape/docId validation.
4. Everything else is denied by default.

## Validation Checklist

Use Rules Simulator:

1. Read `users/{yourUid}/transactions/x` as `gagarwal003@gmail.com` -> allow
2. Read any user data as another Google account -> deny
3. Read `users/{otherUid}/transactions/x` as `gagarwal003@gmail.com` -> deny
4. Write valid `product_mappings/{gid}_{pid}` as `gagarwal003@gmail.com` -> allow
5. Write valid `product_mappings/{gid}_{pid}` as another Google account -> deny
6. Read or write `active_products/{docId}` from the browser -> deny
