# Firestore Security Rules

Add these rules to your Firestore database in the Firebase Console.

Go to: **Firestore Database → Rules → Edit and publish**

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // User transactions - only authenticated users can access their own
    match /users/{userId}/transactions/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // User holdings (future per-user view) - only authenticated users
    match /users/{userId}/holdings/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Active products index - read-only for authenticated users
    // Write-only by backend (via Firestore Admin SDK)
    match /active_products/{document=**} {
      allow read: if request.auth != null;
      allow write: if false;
    }
  }
}
```

## What These Rules Do

1. **User Transactions**: Each user can only read/write transactions in their own `users/{uid}/transactions` collection.
2. **User Holdings**: Supports future per-user portfolio views, isolated by UID.
3. **Active Products Index**: Shared read-only index for the daily price fetch job to discover which products need fetching.

## Important Security Notes

- No anonymous access: `request.auth != null` requires Google login.
- Users cannot see other users' data.
- Backend (GitHub Actions) updates `active_products` via service account (Admin SDK), bypassing client rules.
- All writes to user data are scoped to the authenticated user's UID.

## Testing Rules

Use the Rules Simulator in Firebase Console to test:
1. Test **read** of `users/user123/transactions/txn1` as **user123** → ✅ Allow
2. Test **read** of `users/user456/transactions/txn1` as **user123** → ❌ Deny
3. Test **write** to `active_products/any_doc` as any user → ❌ Deny

