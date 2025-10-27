import 'package:flutter/material.dart';

/// A sample Flutter widget demonstrating a user profile screen
/// This file intentionally exceeds 300 lines to demonstrate the code analyzer
class UserProfileScreen extends StatefulWidget {
  final String userId;
  final bool isEditable;

  const UserProfileScreen({
    Key? key,
    required this.userId,
    this.isEditable = false,
  }) : super(key: key);

  @override
  State<UserProfileScreen> createState() => _UserProfileScreenState();
}

class _UserProfileScreenState extends State<UserProfileScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = true;
  String _userName = '';
  String _userEmail = '';
  String _userBio = '';
  int _followerCount = 0;
  int _followingCount = 0;
  List<Post> _userPosts = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadUserData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadUserData() async {
    setState(() => _isLoading = true);

    // Simulate API call
    await Future.delayed(const Duration(seconds: 2));

    setState(() {
      _userName = 'John Doe';
      _userEmail = 'john.doe@example.com';
      _userBio = 'Flutter developer passionate about creating beautiful UIs';
      _followerCount = 1234;
      _followingCount = 567;
      _userPosts = _generateSamplePosts();
      _isLoading = false;
    });
  }

  List<Post> _generateSamplePosts() {
    return List.generate(
      10,
      (index) => Post(
        id: 'post_$index',
        title: 'Post ${index + 1}',
        content: 'This is the content of post ${index + 1}',
        imageUrl: 'https://picsum.photos/400/300?random=$index',
        likes: (index + 1) * 10,
        comments: (index + 1) * 5,
        timestamp: DateTime.now().subtract(Duration(days: index)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          if (widget.isEditable)
            IconButton(
              icon: const Icon(Icons.edit),
              onPressed: _editProfile,
            ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: _openSettings,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadUserData,
              child: CustomScrollView(
                slivers: [
                  SliverToBoxAdapter(
                    child: _buildProfileHeader(),
                  ),
                  SliverToBoxAdapter(
                    child: _buildStatsSection(),
                  ),
                  SliverToBoxAdapter(
                    child: _buildBioSection(),
                  ),
                  SliverToBoxAdapter(
                    child: _buildTabBar(),
                  ),
                  SliverFillRemaining(
                    child: TabBarView(
                      controller: _tabController,
                      children: [
                        _buildPostsTab(),
                        _buildPhotosTab(),
                        _buildAboutTab(),
                      ],
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildProfileHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Stack(
            children: [
              CircleAvatar(
                radius: 60,
                backgroundImage: NetworkImage(
                  'https://i.pravatar.cc/300?u=${widget.userId}',
                ),
              ),
              if (widget.isEditable)
                Positioned(
                  bottom: 0,
                  right: 0,
                  child: CircleAvatar(
                    radius: 20,
                    backgroundColor: Theme.of(context).primaryColor,
                    child: const Icon(
                      Icons.camera_alt,
                      size: 20,
                      color: Colors.white,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            _userName,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            _userEmail,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.grey,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatsSection() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _buildStatItem('Posts', _userPosts.length.toString()),
          _buildVerticalDivider(),
          _buildStatItem('Followers', _formatCount(_followerCount)),
          _buildVerticalDivider(),
          _buildStatItem('Following', _formatCount(_followingCount)),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, String count) {
    return Column(
      children: [
        Text(
          count,
          style: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            color: Colors.grey[600],
            fontSize: 14,
          ),
        ),
      ],
    );
  }

  Widget _buildVerticalDivider() {
    return Container(
      height: 40,
      width: 1,
      color: Colors.grey[300],
    );
  }

  Widget _buildBioSection() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'About',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            _userBio,
            style: const TextStyle(fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildTabBar() {
    return Container(
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: Colors.grey[300]!),
        ),
      ),
      child: TabBar(
        controller: _tabController,
        labelColor: Theme.of(context).primaryColor,
        unselectedLabelColor: Colors.grey,
        indicatorColor: Theme.of(context).primaryColor,
        tabs: const [
          Tab(icon: Icon(Icons.grid_on), text: 'Posts'),
          Tab(icon: Icon(Icons.photo_library), text: 'Photos'),
          Tab(icon: Icon(Icons.info_outline), text: 'About'),
        ],
      ),
    );
  }

  Widget _buildPostsTab() {
    return ListView.builder(
      padding: const EdgeInsets.all(8),
      itemCount: _userPosts.length,
      itemBuilder: (context, index) {
        final post = _userPosts[index];
        return _buildPostCard(post);
      },
    );
  }

  Widget _buildPostCard(Post post) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (post.imageUrl.isNotEmpty)
            Image.network(
              post.imageUrl,
              width: double.infinity,
              height: 200,
              fit: BoxFit.cover,
            ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  post.title,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(post.content),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Icon(Icons.favorite_border, size: 20, color: Colors.grey[600]),
                    const SizedBox(width: 4),
                    Text('${post.likes}'),
                    const SizedBox(width: 16),
                    Icon(Icons.comment_outlined, size: 20, color: Colors.grey[600]),
                    const SizedBox(width: 4),
                    Text('${post.comments}'),
                    const Spacer(),
                    Text(
                      _formatTimestamp(post.timestamp),
                      style: TextStyle(color: Colors.grey[600], fontSize: 12),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPhotosTab() {
    return GridView.builder(
      padding: const EdgeInsets.all(8),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        crossAxisSpacing: 8,
        mainAxisSpacing: 8,
      ),
      itemCount: _userPosts.length,
      itemBuilder: (context, index) {
        return ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Image.network(
            _userPosts[index].imageUrl,
            fit: BoxFit.cover,
          ),
        );
      },
    );
  }

  Widget _buildAboutTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildAboutItem(Icons.person, 'Name', _userName),
        _buildAboutItem(Icons.email, 'Email', _userEmail),
        _buildAboutItem(Icons.info, 'Bio', _userBio),
        _buildAboutItem(Icons.calendar_today, 'Joined', 'January 2024'),
        _buildAboutItem(Icons.location_on, 'Location', 'San Francisco, CA'),
        _buildAboutItem(Icons.work, 'Occupation', 'Software Developer'),
      ],
    );
  }

  Widget _buildAboutItem(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: Colors.grey[600]),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    color: Colors.grey[600],
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatCount(int count) {
    if (count >= 1000000) {
      return '${(count / 1000000).toStringAsFixed(1)}M';
    } else if (count >= 1000) {
      return '${(count / 1000).toStringAsFixed(1)}K';
    }
    return count.toString();
  }

  String _formatTimestamp(DateTime timestamp) {
    final now = DateTime.now();
    final difference = now.difference(timestamp);

    if (difference.inDays > 0) {
      return '${difference.inDays}d ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours}h ago';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes}m ago';
    } else {
      return 'Just now';
    }
  }

  void _editProfile() {
    // Navigate to edit profile screen
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit Profile'),
        content: const Text('Edit profile functionality would go here'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _openSettings() {
    // Navigate to settings screen
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Settings'),
        content: const Text('Settings functionality would go here'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

/// Model class for a post
class Post {
  final String id;
  final String title;
  final String content;
  final String imageUrl;
  final int likes;
  final int comments;
  final DateTime timestamp;

  Post({
    required this.id,
    required this.title,
    required this.content,
    required this.imageUrl,
    required this.likes,
    required this.comments,
    required this.timestamp,
  });
}
