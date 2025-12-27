<?php

declare(strict_types=1);

namespace Example;

/**
 * Example user service class demonstrating PHP code patterns.
 */
class UserService
{
    private array $users = [];

    public function __construct()
    {
        $this->users = [];
    }

    /**
     * Add a new user to the service.
     */
    public function addUser(string $name, string $email): array
    {
        $user = [
            'id' => count($this->users) + 1,
            'name' => $name,
            'email' => $email,
            'created_at' => date('Y-m-d H:i:s'),
        ];

        $this->users[] = $user;

        return $user;
    }

    /**
     * Find a user by ID.
     */
    public function findById(int $id): ?array
    {
        foreach ($this->users as $user) {
            if ($user['id'] === $id) {
                return $user;
            }
        }

        return null;
    }

    /**
     * Find a user by email address.
     */
    public function findByEmail(string $email): ?array
    {
        foreach ($this->users as $user) {
            if ($user['email'] === $email) {
                return $user;
            }
        }

        return null;
    }

    /**
     * Get all users.
     */
    public function getAllUsers(): array
    {
        return $this->users;
    }

    /**
     * Delete a user by ID.
     */
    public function deleteUser(int $id): bool
    {
        foreach ($this->users as $index => $user) {
            if ($user['id'] === $id) {
                unset($this->users[$index]);
                $this->users = array_values($this->users);
                return true;
            }
        }

        return false;
    }

    /**
     * Update user information.
     */
    public function updateUser(int $id, string $name, string $email): ?array
    {
        foreach ($this->users as $index => $user) {
            if ($user['id'] === $id) {
                $this->users[$index]['name'] = $name;
                $this->users[$index]['email'] = $email;
                return $this->users[$index];
            }
        }

        return null;
    }

    /**
     * Count total users.
     */
    public function countUsers(): int
    {
        return count($this->users);
    }
}
